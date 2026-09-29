#!/usr/bin/env python3
# manage-python.py
"""
manage-python.py, manage user-space installations of CPython.

This manager owns the full lifecycle of self-contained CPython runtimes from
python-build-standalone: acquisition, placement, switching, aliases and
removal. Versions install side by side, named by their full version, and a
pointer file records which version each alias runs and the name each alias
is written under. It is the reference implementation of the proposal
"osat-manager-python Layout, Lifecycle and Aliases" (en/docs/).

This build implements the parts that need no downloads: the pointer file and
alias record, PROVENANCE, platform triple selection, status output and alias
rendering with its ownership check. Install, switch, remove and alias
renaming follow.

Usage:
    manage-python --status             Show aliases, default, installed and archived versions
    manage-python --version            Show this manager's version

What this manager owns (the python-manager management identifier):
    ~/.local/share/python-manager/<version>/          Runtimes, plus PROVENANCE
    ~/.local/share/python-manager/archive/            Verified release tarballs
    ~/.local/share/python-manager/manage-python/      The manager itself
    ~/.config/python-manager/python-manager.env       Pointer, sourced by the aliases
    ~/.local/state/python-manager/                    State and logs
    ~/.local/bin/python, python3.12, ...              Generated aliases

What this manager does not touch:
    ~/.config/python-manager/env                      Operator environment
    Any file in ~/.local/bin it did not write

Requires: Python 3.8+ (standard library only).
"""

from __future__ import annotations

import argparse
import gettext
import os
import platform
import re
import stat
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────────────

MANAGER_VERSION = "0.3.0"
MANAGER_ID      = "python-manager"     # management identifier, owns files
COMMAND         = "manage-python"      # the command users run
SCRIPT_NAME     = "manage-python.py"   # recorded on the by: line of aliases
PROJECT         = "osat-manager-python"

_HERE         = Path(__file__).resolve().parent
TEMPLATES_DIR = _HERE / "scripts"

DIR_MODE  = 0o700
FILE_MODE = 0o600
EXEC_MODE = 0o700

KEY_PREFIX    = "PYTHON_MANAGER_"
DEFAULT       = "DEFAULT"              # alias slot for the generic python
DEFAULT_NAME  = "python"
RESERVED_NAMES = {COMMAND}

VERSION_RE    = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MINOR_RE      = re.compile(r"^(\d+)\.(\d+)$")
ARCHIVE_RE    = re.compile(r"^(\d+\.\d+\.\d+)\+(\d+)$")
ALIAS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
KEY_RE        = re.compile(r"^PYTHON_MANAGER_[A-Z0-9_]+$")
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9._+-]*$")
SHA256_RE     = re.compile(r"^[0-9a-f]{64}$")

# Names Windows refuses as file names, whatever the extension.
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} \
    | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)}

# Messages are translated with gettext. Catalog loading arrives with --lang;
# until then every message passes through untranslated.
_ = gettext.NullTranslations().gettext


class ManagerError(RuntimeError):
    """Raised for any condition that should stop the manager with a clear message."""


# ── Small helpers ─────────────────────────────────────────────────────────────

def log(message: str) -> None:
    print(f"[{COMMAND}] {message}", file=sys.stderr)


def is_windows() -> bool:
    return platform.system() == "Windows"


def version_key(version: str) -> Tuple[int, int, int]:
    match = VERSION_RE.match(version)
    if not match:
        raise ManagerError(_("not a full version: {version!r}").format(version=version))
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def minor_of(version: str) -> str:
    major, minor, _patch = version_key(version)
    return f"{major}.{minor}"


def minor_sort_key(minor: str) -> Tuple[int, int]:
    major, minor_number = minor.split(".")
    return int(major), int(minor_number)


def slot_key(slot: str) -> str:
    """Pointer key suffix for an alias slot: DEFAULT or a minor line, 3.12 -> 3_12."""
    return DEFAULT if slot == DEFAULT else slot.replace(".", "_")


def default_alias_name(slot: str) -> str:
    return DEFAULT_NAME if slot == DEFAULT else f"python{slot}"


# ── Platform paths ────────────────────────────────────────────────────────────

class Paths:
    """Every path the manager uses, resolved once at the boundary.

    `windows`, `environ` and `home` default to the running system and exist
    so tests can resolve either platform's layout inside a scratch directory.
    """

    def __init__(self, windows: Optional[bool] = None,
                 environ: Optional[Mapping[str, str]] = None,
                 home: Optional[Path] = None) -> None:
        self.windows = is_windows() if windows is None else windows
        env = os.environ if environ is None else environ
        self.home = Path.home() if home is None else home

        if self.windows:
            local = Path(env.get("LOCALAPPDATA") or self.home / "AppData" / "Local")
            roaming = Path(env.get("APPDATA") or self.home / "AppData" / "Roaming")
            self._display_roots = [(str(local), "%LOCALAPPDATA%"),
                                   (str(roaming), "%APPDATA%")]
            self.share_dir = local / MANAGER_ID
            self.bin_dir = local / "Programs"
            self.pointer_dir = self.share_dir
            self.config_dir = roaming / MANAGER_ID
            self.state_dir = self.share_dir / "logs"
            self.pointer_files = {
                "cmd": self.pointer_dir / f"{MANAGER_ID}.env.cmd",
                "ps1": self.pointer_dir / f"{MANAGER_ID}.env.ps1",
            }
            self.operator_env = self.config_dir / "env.cmd"
        else:
            data = Path(env.get("XDG_DATA_HOME") or self.home / ".local" / "share")
            bins = Path(env.get("XDG_BIN_HOME") or self.home / ".local" / "bin")
            cfg = Path(env.get("XDG_CONFIG_HOME") or self.home / ".config")
            state = Path(env.get("XDG_STATE_HOME") or self.home / ".local" / "state")
            self._display_roots = [(str(self.home), "~")]
            self.share_dir = data / MANAGER_ID
            self.bin_dir = bins
            self.pointer_dir = cfg / MANAGER_ID
            self.config_dir = cfg / MANAGER_ID
            self.state_dir = state / MANAGER_ID
            self.pointer_files = {"posix": self.pointer_dir / f"{MANAGER_ID}.env"}
            self.operator_env = self.config_dir / "env"

        self.archive_dir = self.share_dir / "archive"
        self.manager_dir = self.share_dir / COMMAND
        self.log_file = self.state_dir / f"{COMMAND}.log"

    @property
    def pointer_file(self) -> Path:
        """The pointer file the manager reads; on Windows the .cmd twin."""
        return self.pointer_files["cmd" if self.windows else "posix"]

    def alias_files(self, name: str) -> List[Tuple[Path, str]]:
        """(path, format) for each file that makes up alias `name`."""
        if self.windows:
            return [(self.bin_dir / f"{name}.cmd", "cmd"),
                    (self.bin_dir / f"{name}.ps1", "ps1")]
        return [(self.bin_dir / name, "posix")]

    def runtime_dir(self, version: str) -> Path:
        return self.share_dir / version

    def display(self, path: Path) -> str:
        """A path as a person reads it: ~ on POSIX, %LOCALAPPDATA% on Windows."""
        text = str(path)
        for root, label in self._display_roots:
            if text == root or text.startswith(root + os.sep) or text.startswith(root + "/"):
                return label + text[len(root):]
        return text


# ── Filesystem ────────────────────────────────────────────────────────────────

def ensure_dir(path: Path, windows: bool) -> None:
    """Create a manager-owned directory with owner-only permissions, and fail
    explicitly if an existing one is broader than that. Windows directories
    inherit owner-only ACLs from the profile."""
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if windows:
        return
    if created:
        path.chmod(DIR_MODE)
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ManagerError(_(
            "{path} has permissions {mode}, broader than the owner-only {want} "
            "this collection requires; fix the permissions and rerun"
        ).format(path=path, mode=oct(mode), want=oct(DIR_MODE)))


def atomic_write_text(path: Path, text: str, *, newline: str = "\n",
                      mode: int = FILE_MODE, windows: bool = False) -> None:
    """Write `text` to a temporary file beside `path` and rename it into place,
    so a reader sees either the old file or the new one, never a partial one.
    `newline` is what each "\\n" in `text` becomes on disk."""
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                                    dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if not windows:
            os.chmod(tmp_name, mode)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── Pointer file and alias record ─────────────────────────────────────────────

# One line of each pointer syntax. Values are restricted to SAFE_VALUE_RE on
# write, so a value never needs quoting beyond the surrounding double quotes.
_POINTER_LINE = {
    "posix": re.compile(r'^(PYTHON_MANAGER_[A-Z0-9_]+)="([^"]*)"$'),
    "cmd":   re.compile(r'^set "(PYTHON_MANAGER_[A-Z0-9_]+)=([^"]*)"$', re.IGNORECASE),
    "ps1":   re.compile(r'^\$env:(PYTHON_MANAGER_[A-Z0-9_]+)\s*=\s*"([^"]*)"$', re.IGNORECASE),
}
_POINTER_COMMENT = {
    "posix": ("#",),
    "cmd":   ("rem ", "rem\t", "::"),
    "ps1":   ("#",),
}
_POINTER_FORMAT = {
    "posix": ('# {line}', '{key}="{value}"'),
    "cmd":   ('rem {line}', 'set "{key}={value}"'),
    "ps1":   ('# {line}', '$env:{key} = "{value}"'),
}
_POINTER_NEWLINE = {"posix": "\n", "cmd": "\r\n", "ps1": "\r\n"}


class PointerRecord:
    """Which version each alias runs, and the name each alias is written under.

    `default` is the full version behind the generic alias, `lines` maps each
    minor line ("3.12") to the full version its versioned alias runs, and
    `aliases` maps an alias slot (DEFAULT or a minor line) to a name the user
    chose. Slots without a recorded name use the default names, python and
    python3.12. `extra` keeps PYTHON_MANAGER_* keys this version does not
    know, so a rewrite never drops what a newer manager recorded.
    """

    def __init__(self, default: Optional[str] = None,
                 lines: Optional[Dict[str, str]] = None,
                 aliases: Optional[Dict[str, str]] = None,
                 extra: Optional[Dict[str, str]] = None) -> None:
        self.default = default
        self.lines = dict(lines or {})
        self.aliases = dict(aliases or {})
        self.extra = dict(extra or {})

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PointerRecord):
            return NotImplemented
        return self.to_items() == other.to_items()

    def __repr__(self) -> str:
        return f"PointerRecord({self.to_items()!r})"

    def alias_name(self, slot: str) -> str:
        return self.aliases.get(slot) or default_alias_name(slot)

    def active_slots(self) -> List[str]:
        """Slots that currently have an alias: DEFAULT if set, then each minor line."""
        slots = [DEFAULT] if self.default else []
        return slots + sorted(self.lines, key=minor_sort_key)

    def switch(self, version: str) -> None:
        """Point the generic alias and the version's minor line at `version`."""
        version_key(version)
        self.default = version
        self.lines[minor_of(version)] = version

    # ── keys ──

    def to_items(self) -> List[Tuple[str, str]]:
        """Pointer keys in file order: versions, then alias names, then unknown keys."""
        items: List[Tuple[str, str]] = []
        if self.default:
            items.append((KEY_PREFIX + DEFAULT, self.default))
        for minor in sorted(self.lines, key=minor_sort_key):
            items.append((KEY_PREFIX + slot_key(minor), self.lines[minor]))
        alias_slots = self.active_slots()
        alias_slots += sorted((s for s in self.aliases if s not in alias_slots), key=_slot_order)
        for slot in alias_slots:
            items.append((f"{KEY_PREFIX}ALIAS_{slot_key(slot)}", self.alias_name(slot)))
        items.extend(sorted(self.extra.items()))
        return items

    @classmethod
    def from_items(cls, items: List[Tuple[str, str]]) -> "PointerRecord":
        record = cls()
        for key, value in items:
            suffix = key[len(KEY_PREFIX):]
            if suffix == DEFAULT:
                record.default = value
            elif suffix.startswith("ALIAS_"):
                record.aliases[_slot_from_suffix(suffix[len("ALIAS_"):], key)] = value
            elif re.fullmatch(r"\d+_\d+", suffix):
                record.lines[suffix.replace("_", ".")] = value
            else:
                record.extra[key] = value
        record.validate()
        return record

    def validate(self) -> None:
        """Refuse a record the aliases could not use safely."""
        for key, value in self.to_items():
            if not KEY_RE.match(key) or not SAFE_VALUE_RE.match(value):
                raise ManagerError(_("pointer key {key} has an unsafe value {value!r}")
                                   .format(key=key, value=value))
        for minor, version in self.lines.items():
            if not MINOR_RE.match(minor) or minor_of(version) != minor:
                raise ManagerError(_("pointer names {version} for the {minor} line")
                                   .format(version=version, minor=minor))
        if self.default is not None:
            line_version = self.lines.get(minor_of(self.default))
            if line_version != self.default:
                raise ManagerError(_(
                    "pointer default {default} is not the version of its minor "
                    "line ({line}); python and python{minor} must agree"
                ).format(default=self.default, line=line_version or _("unset"),
                         minor=minor_of(self.default)))
        seen: Dict[str, str] = {}
        for slot in set(self.active_slots()) | set(self.aliases):
            name = self.alias_name(slot)
            check_alias_name(name)
            # Windows and macOS filesystems are case-insensitive by default.
            folded = name.casefold()
            if folded in seen and seen[folded] != slot:
                raise ManagerError(_("alias name {name} is used twice").format(name=name))
            seen[folded] = slot


def _slot_order(slot: str) -> Tuple[int, int, int]:
    """DEFAULT first, then minor lines in numeric order."""
    return (0, 0, 0) if slot == DEFAULT else (1,) + minor_sort_key(slot)


def _slot_from_suffix(suffix: str, key: str) -> str:
    if suffix == DEFAULT:
        return DEFAULT
    if re.fullmatch(r"\d+_\d+", suffix):
        return suffix.replace("_", ".")
    raise ManagerError(_("unknown alias key {key}").format(key=key))


def check_alias_name(name: str) -> None:
    if (not ALIAS_NAME_RE.match(name)
            or name in RESERVED_NAMES
            or name.split(".")[0].casefold() in WINDOWS_RESERVED
            or name.casefold().endswith((".cmd", ".ps1", ".exe", ".bat"))):
        raise ManagerError(_(
            "{name!r} cannot be an alias name: use letters, digits, '.', '_', "
            "'+' or '-', starting with a letter or digit"
        ).format(name=name))


def render_pointer(record: PointerRecord, fmt: str, paths: Paths) -> str:
    """The pointer in one syntax, as text with "\\n" line endings."""
    record.validate()
    comment, assignment = _POINTER_FORMAT[fmt]
    header = [
        paths.display(paths.pointer_files[fmt]) if fmt in paths.pointer_files
        else f"{MANAGER_ID}.env",
        _("Generated by {script}. Read by the aliases at runtime.").format(script=SCRIPT_NAME),
        _("Operator environment belongs in {env},").format(env=paths.display(
            paths.operator_env if fmt != "ps1" else paths.config_dir / "env.ps1")),
        _("which this manager never touches."),
    ]
    lines = [comment.format(line=line) for line in header]
    in_aliases = False
    for key, value in record.to_items():
        if key.startswith(KEY_PREFIX + "ALIAS_") and not in_aliases:
            lines.append("")
            in_aliases = True
        lines.append(assignment.format(key=key, value=value))
    return "\n".join(lines) + "\n"


def parse_pointer(text: str, fmt: str) -> PointerRecord:
    """Parse a pointer in one syntax. Blank lines and comments are skipped;
    any other line that is not a PYTHON_MANAGER_* assignment is an error."""
    pattern = _POINTER_LINE[fmt]
    comments = _POINTER_COMMENT[fmt]
    items: List[Tuple[str, str]] = []
    for number, raw in enumerate(text.lstrip("﻿").splitlines(), start=1):
        line = raw.strip()
        lowered = line.lower()
        if not line or lowered == "rem" or lowered.startswith(comments) or lowered == "@echo off":
            continue
        match = pattern.match(line)
        if not match:
            raise ManagerError(_("pointer line {number} is not a PYTHON_MANAGER_* setting: {line}")
                               .format(number=number, line=line))
        items.append((match.group(1).upper(), match.group(2)))
    return PointerRecord.from_items(items)


def read_pointer(paths: Paths) -> PointerRecord:
    """The pointer as recorded, or an empty record when none has been written."""
    path = paths.pointer_file
    fmt = "cmd" if paths.windows else "posix"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PointerRecord()
    try:
        return parse_pointer(text, fmt)
    except ManagerError as error:
        raise ManagerError(f"{paths.display(path)}: {error}") from None


def write_pointer(record: PointerRecord, paths: Paths) -> None:
    """Write every pointer file for the platform, each one atomically."""
    ensure_dir(paths.pointer_dir, paths.windows)
    for fmt, path in paths.pointer_files.items():
        atomic_write_text(path, render_pointer(record, fmt, paths),
                          newline=_POINTER_NEWLINE[fmt], windows=paths.windows)


# ── PROVENANCE ────────────────────────────────────────────────────────────────

# The first five keys are the ones restic-tool writes, in the same order, so
# one parser reads both. Runtimes add three more.
PROVENANCE_KEYS = ("manager", "asset", "sha256", "source", "installed")
RUNTIME_PROVENANCE_KEYS = PROVENANCE_KEYS + ("version", "build", "triple")


def utc_timestamp(now: Optional[datetime] = None) -> str:
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_provenance(fields: Mapping[str, str], keys: Tuple[str, ...]) -> str:
    missing = [key for key in keys if not fields.get(key)]
    if missing:
        raise ManagerError(_("PROVENANCE is missing {keys}").format(keys=", ".join(missing)))
    for key in keys:
        if any(ch in fields[key] for ch in "\r\n"):
            raise ManagerError(_("PROVENANCE value for {key} spans lines").format(key=key))
    if not SHA256_RE.match(fields["sha256"]):
        raise ManagerError(_("PROVENANCE sha256 is not 64 lowercase hexadecimal characters"))
    return "".join(f"{key}: {fields[key]}\n" for key in keys)


def write_provenance(directory: Path, *, asset: str, sha256: str, source: str,
                     version: Optional[str] = None, build: Optional[str] = None,
                     triple: Optional[str] = None, now: Optional[datetime] = None,
                     windows: bool = False) -> Path:
    """Write PROVENANCE into `directory`. A runtime passes version, build and
    triple; a manager version passes none of them and gets the first five keys."""
    runtime_fields = (version, build, triple)
    if any(runtime_fields) and not all(runtime_fields):
        raise ManagerError(_("a runtime's PROVENANCE needs version, build and triple together"))
    fields = {
        "manager": f"{COMMAND} {MANAGER_VERSION}",
        "asset": asset,
        "sha256": sha256.lower(),
        "source": source,
        "installed": utc_timestamp(now),
    }
    keys = PROVENANCE_KEYS
    if version:
        version_key(version)
        fields.update(version=version, build=str(build), triple=str(triple))
        keys = RUNTIME_PROVENANCE_KEYS
    path = directory / "PROVENANCE"
    atomic_write_text(path, render_provenance(fields, keys), windows=windows)
    return path


def parse_provenance(text: str) -> Dict[str, str]:
    """`key: value` pairs. Unknown keys are kept for the caller to ignore;
    for a repeated key the first value wins; lines without a colon are skipped."""
    fields: Dict[str, str] = {}
    for line in text.lstrip("﻿").splitlines():
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not key or key in fields:
            continue
        fields[key] = value.strip()
    return fields


def read_provenance(directory: Path) -> Dict[str, str]:
    """PROVENANCE in `directory`, or an empty dict when there is none."""
    try:
        return parse_provenance((directory / "PROVENANCE").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


# ── Platform triple ───────────────────────────────────────────────────────────

_ARCH_NAMES = {
    "x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64",
    "aarch64": "aarch64", "arm64": "aarch64",
    "armv7l": "armv7", "armv7": "armv7",
    "ppc64le": "ppc64le", "riscv64": "riscv64", "s390x": "s390x",
    "i386": "i686", "i686": "i686", "x86": "i686",
}

# (system, arch, libc) -> python-build-standalone triple. The x86-64 entries
# are the baseline builds, never the x86_64_v2/v3/v4 variants, so a runtime
# restored from the archive onto an older machine still starts.
TRIPLES = {
    ("Linux", "x86_64", "gnu"):   "x86_64-unknown-linux-gnu",
    ("Linux", "aarch64", "gnu"):  "aarch64-unknown-linux-gnu",
    ("Linux", "armv7", "gnu"):    "armv7-unknown-linux-gnueabihf",
    ("Linux", "ppc64le", "gnu"):  "ppc64le-unknown-linux-gnu",
    ("Linux", "riscv64", "gnu"):  "riscv64-unknown-linux-gnu",
    ("Linux", "s390x", "gnu"):    "s390x-unknown-linux-gnu",
    ("Linux", "x86_64", "musl"):  "x86_64-unknown-linux-musl",
    ("Linux", "aarch64", "musl"): "aarch64-unknown-linux-musl",
    ("Darwin", "x86_64", None):   "x86_64-apple-darwin",
    ("Darwin", "aarch64", None):  "aarch64-apple-darwin",
    ("Windows", "x86_64", None):  "x86_64-pc-windows-msvc",
    ("Windows", "aarch64", None): "aarch64-pc-windows-msvc",
    ("Windows", "i686", None):    "i686-pc-windows-msvc",
}

PT_INTERP = 3


def elf_interpreter(path: str) -> Optional[str]:
    """The program interpreter (dynamic loader) an ELF executable names, or
    None if the file is not ELF, is static, or cannot be read."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(64)
            if len(header) < 52 or header[:4] != b"\x7fELF":
                return None
            is_64 = header[4] == 2
            order = "<" if header[5] == 1 else ">"
            if is_64:
                phoff, = struct.unpack_from(order + "Q", header, 0x20)
                phentsize, phnum = struct.unpack_from(order + "HH", header, 0x36)
            else:
                phoff, = struct.unpack_from(order + "I", header, 0x1C)
                phentsize, phnum = struct.unpack_from(order + "HH", header, 0x2A)
            if phnum > 512 or phentsize < (56 if is_64 else 32):
                return None
            for index in range(phnum):
                handle.seek(phoff + index * phentsize)
                entry = handle.read(phentsize)
                if len(entry) < phentsize:
                    return None
                p_type, = struct.unpack_from(order + "I", entry, 0)
                if p_type != PT_INTERP:
                    continue
                if is_64:
                    offset, = struct.unpack_from(order + "Q", entry, 8)
                    size, = struct.unpack_from(order + "Q", entry, 32)
                else:
                    offset, = struct.unpack_from(order + "I", entry, 4)
                    size, = struct.unpack_from(order + "I", entry, 16)
                if size > 4096:
                    return None
                handle.seek(offset)
                return handle.read(size).split(b"\0", 1)[0].decode("utf-8", "replace")
    except (OSError, struct.error):
        return None
    return None


def detect_libc(libc_ver: Callable[[], Tuple[str, str]] = platform.libc_ver,
                interpreter_of: Callable[[str], Optional[str]] = elf_interpreter,
                exists: Callable[[str], bool] = os.path.exists) -> str:
    """"gnu" or "musl" for the Linux host.

    A running interpreter linked against glibc settles it. Otherwise the
    loader named by /bin/sh does: it is native to the host on every
    distribution, and it is not fooled by a musl loader installed alongside
    glibc (Debian's musl package) or by NixOS keeping its loader in the store.
    """
    if libc_ver()[0] == "glibc":
        return "gnu"
    loader = interpreter_of("/bin/sh")
    if loader:
        return "musl" if os.path.basename(loader).startswith("ld-musl") else "gnu"
    return "musl" if exists("/etc/alpine-release") else "gnu"


def rosetta_translated(run: Callable[..., "subprocess.CompletedProcess[str]"] = subprocess.run) -> bool:
    """True when this process is an Intel build running under Rosetta 2.

    sysctl.proc_translated is 1 under Rosetta, 0 on Apple Silicon natively,
    and absent on Intel Macs (-i prints nothing rather than failing)."""
    try:
        result = run(["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"],
                     capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "1"


def select_triple(system: str, machine: str, libc: Optional[str] = None,
                  translated: bool = False) -> str:
    """The python-build-standalone triple for a platform, or ManagerError."""
    arch = _ARCH_NAMES.get(machine.lower(), machine.lower())
    if system == "Darwin" and arch == "x86_64" and translated:
        arch = "aarch64"
    key = (system, arch, libc if system == "Linux" else None)
    try:
        return TRIPLES[key]
    except KeyError:
        described = f"{system}/{machine}" + (f" ({libc})" if system == "Linux" else "")
        supported = ", ".join(
            f"{s}/{a}" + (f" ({l})" if l else "") for s, a, l in TRIPLES)
        raise ManagerError(_(
            "python-build-standalone publishes no runtime for {platform}. "
            "Supported: {supported}."
        ).format(platform=described, supported=supported)) from None


def detect_triple() -> str:
    system, machine = platform.system(), platform.machine()
    libc = detect_libc() if system == "Linux" else None
    translated = system == "Darwin" and rosetta_translated()
    return select_triple(system, machine, libc, translated)


# ── Filesystem inventory ──────────────────────────────────────────────────────

def installed_versions(paths: Paths) -> List[str]:
    """Runtime directories on disk, newest first. archive/ and manage-python/
    are excluded because they are not full versions."""
    if not paths.share_dir.is_dir():
        return []
    found = [entry.name for entry in paths.share_dir.iterdir()
             if entry.is_dir() and VERSION_RE.match(entry.name)]
    return sorted(found, key=version_key, reverse=True)


def archived_builds(paths: Paths) -> List[str]:
    """Archive entries such as 3.12.12+20260715, newest first."""
    if not paths.archive_dir.is_dir():
        return []
    found = [entry.name for entry in paths.archive_dir.iterdir()
             if entry.is_dir() and ARCHIVE_RE.match(entry.name)]

    def key(name: str) -> Tuple[Tuple[int, int, int], int]:
        version, build = ARCHIVE_RE.match(name).groups()  # type: ignore[union-attr]
        return version_key(version), int(build)
    return sorted(found, key=key, reverse=True)


# ── Status ────────────────────────────────────────────────────────────────────

class LineStatus:
    """One minor line as --status shows it."""

    def __init__(self, minor: str) -> None:
        self.minor = minor
        self.aliases: List[str] = []
        self.default: Optional[str] = None
        self.installed: List[str] = []
        self.archived: List[str] = []


def collect_status(paths: Paths, record: PointerRecord) -> Tuple[List[LineStatus], List[str]]:
    """Status per minor line, built from the runtime and archive directories
    on disk and the pointer, plus warnings where they disagree."""
    installed = installed_versions(paths)
    archived = archived_builds(paths)
    installed_set = set(installed)
    minors = ({minor_of(v) for v in installed} | set(record.lines)
              | {minor_of(ARCHIVE_RE.match(b).group(1)) for b in archived})  # type: ignore[union-attr]
    warnings: List[str] = []
    lines: List[LineStatus] = []
    for minor in sorted(minors, key=minor_sort_key):
        line = LineStatus(minor)
        line.default = record.lines.get(minor)
        if line.default:
            line.aliases.append(record.alias_name(minor))
            if record.default and minor_of(record.default) == minor:
                line.aliases.append(record.alias_name(DEFAULT))
            if line.default not in installed_set:
                warnings.append(_("the pointer names {version} for {alias}, but it is not installed")
                                .format(version=line.default, alias=record.alias_name(minor)))
        line.installed = [v for v in installed if minor_of(v) == minor and v != line.default]
        line.archived = [b for b in archived
                         if minor_of(ARCHIVE_RE.match(b).group(1)) == minor  # type: ignore[union-attr]
                         and ARCHIVE_RE.match(b).group(1) not in installed_set]  # type: ignore[union-attr]
        lines.append(line)
    for slot in record.active_slots():
        name = record.alias_name(slot)
        for alias_path, _fmt in paths.alias_files(name):
            if not alias_path.exists():
                warnings.append(_("alias {name} is recorded in the pointer, but {path} does not exist")
                                .format(name=name, path=paths.display(alias_path)))
    return lines, warnings


def format_status(lines: List[LineStatus]) -> str:
    if not lines:
        return _("No Python versions installed.") + "\n"
    labels = {"aliases": _("aliases"), "default": _("default"),
              "installed": _("installed"), "archived": _("archived")}
    width = max(len(label) for label in labels.values()) + 3
    out: List[str] = []
    for line in lines:
        if out:
            out.append("")
        out.append(line.minor)
        rows = [("aliases", "  ", line.aliases),
                ("default", "    ", [line.default] if line.default else []),
                ("installed", "    ", line.installed),
                ("archived", "    ", line.archived)]
        for name, indent, values in rows:
            if values:
                out.append(f"{indent}{labels[name].ljust(width)}{'  '.join(values)}")
    return "\n".join(out) + "\n"


# ── Aliases ───────────────────────────────────────────────────────────────────

ALIAS_TEMPLATES = {
    "posix": ("nix/alias.template", "#"),
    "cmd":   ("windows/alias.cmd.template", "rem"),
    "ps1":   ("windows/alias.ps1.template", "#"),
}
_TOKEN_RE = re.compile(r"@[A-Z][A-Z_]*@")
OWNERSHIP_WINDOW = 4096


def read_template(fmt: str, templates_dir: Path = TEMPLATES_DIR) -> str:
    relpath, _comment = ALIAS_TEMPLATES[fmt]
    path = templates_dir / relpath
    if not path.is_file():
        raise ManagerError(_("alias template not found at {path}").format(path=path))
    return path.read_text(encoding="utf-8")


def render_alias(template: str, comment: str, alias_path: str, version_key_name: str) -> str:
    """Render an alias from its template. As in restic-tool, the template
    declares `generates`; the written alias records `generated`, stamped with
    its maker on the by: line that the ownership check looks for."""
    rendered = (template.replace("@ALIAS_PATH@", alias_path)
                        .replace("@VERSION_KEY@", version_key_name))
    leftover = _TOKEN_RE.search(rendered)
    if leftover:
        raise ManagerError(_("alias template has an unknown token {token}")
                           .format(token=leftover.group(0)))
    generates = f"{comment} generates\n"
    if generates not in rendered:
        raise ManagerError(_("alias template has no '{marker}' header line")
                           .format(marker=generates.strip()))
    rendered = rendered.replace(generates, f"{comment} generated\n", 1)
    marker = f"{comment}   path: "
    at = rendered.find(marker, rendered.find(f"{comment} generated\n"))
    line_end = rendered.find("\n", at) + 1
    return rendered[:line_end] + f"{comment}   by: {SCRIPT_NAME}\n" + rendered[line_end:]


def alias_owner(path: Path) -> str:
    """"absent", "ours" or "foreign" for a file at an alias path.

    A file is ours only if its header block, the comment lines before the
    first command, has a `generated` section whose by: line names this
    script. Symbolic links, binaries and anything unreadable are foreign:
    the manager never writes those, so it never overwrites them."""
    if path.is_symlink():
        return "foreign"
    if not path.exists():
        return "absent"
    try:
        with open(path, "rb") as handle:
            head = handle.read(OWNERSHIP_WINDOW).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return "foreign"
    in_generated = False
    for raw in head.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith("#!") or lowered == "@echo off":
            continue
        if lowered == "rem" or lowered.startswith(("rem ", "rem\t")):
            body = line[3:]
        elif line.startswith("#"):
            body = line[1:]
        else:
            break                                   # first command ends the header
        if body.strip() == "generated":
            in_generated = True
        elif body.strip() in ("source", "generates"):
            in_generated = False
        elif in_generated and body.strip() == f"by: {SCRIPT_NAME}":
            return "ours"
    return "foreign"


def check_alias_writable(paths: Paths, slot: str, name: str) -> None:
    """Refuse, before anything is written, if any file of alias `name` exists
    and was not written by this manager."""
    for path, _fmt in paths.alias_files(name):
        if alias_owner(path) == "foreign":
            raise ManagerError(_(
                "{path} already exists and was not written by {command}. "
                "Leave it in place and choose another name, for example: "
                "{command} --alias {current}=<new-name>"
            ).format(path=paths.display(path), command=COMMAND,
                     current=default_alias_name(slot)))


def write_alias(paths: Paths, slot: str, name: str,
                templates_dir: Path = TEMPLATES_DIR) -> List[Path]:
    """Render and atomically write every file of one alias, after checking
    that none of them belongs to someone else."""
    check_alias_name(name)
    check_alias_writable(paths, slot, name)
    # The bin directory is shared with the distribution and other tools, so
    # it is created if absent but never made owner-only.
    paths.bin_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path, fmt in paths.alias_files(name):
        _relpath, comment = ALIAS_TEMPLATES[fmt]
        text = render_alias(read_template(fmt, templates_dir), comment,
                            paths.display(path), KEY_PREFIX + slot_key(slot))
        atomic_write_text(path, text, newline=_POINTER_NEWLINE[fmt],
                          mode=EXEC_MODE, windows=paths.windows)
        written.append(path)
    return written


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status(paths: Paths) -> int:
    record = read_pointer(paths)
    lines, warnings = collect_status(paths, record)
    sys.stdout.write(format_status(lines))
    for warning in warnings:
        log(_("warning: {message}").format(message=warning))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog=COMMAND,
        description=_("Manage user-space installations of CPython."),
    )
    parser.add_argument("--status", action="store_true",
                        help=_("Show aliases, default, installed and archived versions."))
    parser.add_argument("--version", action="store_true",
                        help=_("Show this manager's version and exit."))
    args = parser.parse_args(argv)

    try:
        if args.version:
            print(f"{COMMAND} {MANAGER_VERSION}")
            return 0
        if args.status:
            return cmd_status(Paths())
    except ManagerError as error:
        log(_("ERROR: {message}").format(message=error))
        return 1
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
