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

Every download is verified against the release's SHA256SUMS before it is
extracted, every runtime is health-checked before it is used, and every
verified release tarball is kept in a local archive, so reinstalling a
version works offline (archive-first resolution).

Usage:
    manage-python --install [SPEC]     Install and switch to a runtime (default: latest of the default minor line)
                                       SPEC is 3.13, 3.12.14 or 3.12.14+20260924 (no API call)
    manage-python --switch VERSION     Make an installed version the one python and its minor alias run
    manage-python --status             Show aliases, default, installed and archived versions
    manage-python --remove VERSION     Remove an installed version no alias needs (archive is kept)
    manage-python --alias OLD=NEW      Rename an alias
    manage-python --version            Show this manager's version

What this manager owns (the python-manager management identifier):
    ~/.local/share/python-manager/<version>/          Runtimes, plus PROVENANCE
    ~/.local/share/python-manager/archive/            Verified release tarballs
    ~/.local/share/python-manager/manage-python/      The manager itself
    ~/.config/python-manager/python-manager.env       Pointer, sourced by the aliases
    ~/.local/state/python-manager/                    State and logs
    ~/.local/bin/python, python3.12, manage-python    Generated aliases

What this manager does not touch:
    ~/.config/python-manager/env                      Operator environment
    Any file in ~/.local/bin it did not write

Requires: Python 3.8+ (standard library only), and network access when a
requested runtime is not already in the local archive.
"""

from __future__ import annotations

import argparse
import copy
import gettext
import hashlib
import json
import locale
import os
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────────────

MANAGER_ID  = "python-manager"     # management identifier, owns files
COMMAND     = "manage-python"      # the command users run
SCRIPT_NAME = "manage-python.py"   # recorded on the by: line of aliases
PROJECT     = "osat-manager-python"

_HERE         = Path(__file__).resolve().parent
TEMPLATES_DIR = _HERE / "scripts"

GITHUB_REPO   = "astral-sh/python-build-standalone"
API_BASE      = f"https://api.github.com/repos/{GITHUB_REPO}"
DOWNLOAD_BASE = f"https://github.com/{GITHUB_REPO}/releases/download"
FLAVOR        = "install_only_stripped"
RELEASE_PAGES = 5                  # pages of 30 releases searched for a full version

LOCALE_DOMAIN = COMMAND
LOCALE_DIR    = _HERE / "locale"
BUILTIN_LANG  = "en"               # messages are written in English, the source language

# In sandbox mode (tests, smoke runs, end-to-end runs) the manager refuses to
# change anything unless every location it writes is set explicitly and lies
# outside the account's real home directory.
SANDBOX_VAR          = "PYTHON_MANAGER_SANDBOX"
POSIX_SANDBOX_VARS   = ("HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_BIN_HOME")
WINDOWS_SANDBOX_VARS = ("LOCALAPPDATA", "APPDATA")

POSIX_MODES = os.name != "nt"     # whether permission bits mean anything on this machine
DIR_MODE  = 0o700
FILE_MODE = 0o600
EXEC_MODE = 0o700

KEY_PREFIX   = "PYTHON_MANAGER_"
DEFAULT      = "DEFAULT"           # alias slot for the generic python
SELF         = "SELF"              # alias slot for the manager itself
DEFAULT_NAME = "python"

VERSION_RE    = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MINOR_RE      = re.compile(r"^(\d+)\.(\d+)$")
ARCHIVE_RE    = re.compile(r"^(\d+\.\d+\.\d+)\+(\d+)$")
ALIAS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
KEY_RE        = re.compile(r"^PYTHON_MANAGER_[A-Z0-9_]+$")
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9._+-]*$")
SHA256_RE     = re.compile(r"^[0-9a-f]{64}$")
LANG_RE       = re.compile(r"^[A-Za-z]{2,3}(?:[_-][A-Za-z0-9]{2,8})?$")

# Names Windows refuses as file names, whatever the extension.
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} \
    | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)}

# Messages are translated with gettext; set_language() replaces this with the
# chosen catalog before any command runs.
_ = gettext.NullTranslations().gettext


class ManagerError(RuntimeError):
    """Raised for any condition that should stop the manager with a clear message."""


class UsageError(ManagerError):
    """A command given incorrectly; the manager exits with 2."""


# ── Language ──────────────────────────────────────────────────────────────────

def normalise_lang(value: str) -> str:
    """fr_CA.UTF-8@euro -> fr_CA; C and POSIX -> en."""
    code = value.split(".", 1)[0].split("@", 1)[0].replace("-", "_")
    return BUILTIN_LANG if code in ("", "C", "POSIX") else code


def system_lang(environ: Mapping[str, str],
                windows_ui_lang: Optional[Callable[[], Optional[str]]] = None) -> Optional[str]:
    """The user's message language: the variables gettext itself reads on
    POSIX, the Windows display language otherwise."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = environ.get(var, "").split(":", 1)[0]
        if value:
            return normalise_lang(value)
    probe = windows_ui_lang or _windows_ui_lang
    return probe()


def _windows_ui_lang() -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None
    name = locale.windows_locale.get(lcid)
    return normalise_lang(name) if name else None


def available_langs(locale_dir: Path = LOCALE_DIR) -> List[str]:
    """English, plus every language with a compiled catalog shipped beside the manager."""
    found = {BUILTIN_LANG}
    if locale_dir.is_dir():
        found |= {entry.name for entry in locale_dir.iterdir()
                  if (entry / "LC_MESSAGES" / f"{LOCALE_DOMAIN}.mo").is_file()}
    return sorted(found)


def choose_lang(option: Optional[str], environ: Mapping[str, str],
                locale_dir: Path = LOCALE_DIR,
                windows_ui_lang: Optional[Callable[[], Optional[str]]] = None) -> Tuple[str, Optional[str]]:
    """The language to use and, when a requested one has no catalog, a warning.

    Order: --lang, then PYTHON_MANAGER_LANG, then the system locale, then
    English. A language is matched exactly, then by its first part (fr_CA -> fr)."""
    if option is not None and not LANG_RE.match(option):
        raise UsageError(_("--lang takes a language code such as fr or pt_BR, not {lang!r}")
                         .format(lang=option))
    available = available_langs(locale_dir)
    requests = [(option, True), (environ.get("PYTHON_MANAGER_LANG") or None, True),
                (system_lang(environ, windows_ui_lang), False)]
    for requested, explicit in requests:
        if not requested:
            continue
        code = normalise_lang(requested)
        for candidate in (code, code.split("_", 1)[0]):
            if candidate in available:
                return candidate, None
        if explicit:
            return BUILTIN_LANG, _("no {lang} translation is available; using English").format(lang=code)
    return BUILTIN_LANG, None


def set_language(lang: str, locale_dir: Path = LOCALE_DIR) -> None:
    global _
    if lang == BUILTIN_LANG:
        _ = gettext.NullTranslations().gettext
        return
    _ = gettext.translation(LOCALE_DOMAIN, localedir=str(locale_dir), languages=[lang],
                            fallback=True).gettext


# ── Sandbox ───────────────────────────────────────────────────────────────────

def sandbox_mode() -> bool:
    return bool(os.environ.get(SANDBOX_VAR))


CSIDL_APPDATA, CSIDL_LOCAL_APPDATA, CSIDL_PROFILE = 0x001A, 0x001C, 0x0028


def _windows_folder(csidl: int) -> Optional[Path]:
    """A Windows shell folder from the user's profile, not from %LOCALAPPDATA%
    or %APPDATA%, which a sandbox overrides."""
    try:
        import ctypes
        buffer = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) == 0:  # type: ignore[attr-defined]
            return Path(buffer.value)
    except (AttributeError, OSError):
        pass
    return None


def real_home() -> Path:
    """The account's home directory from the system, never from $HOME, which
    a sandbox overrides."""
    if os.name == "nt":
        return _windows_folder(CSIDL_PROFILE) or Path(os.environ.get("USERPROFILE") or Path.home())
    import pwd
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def protected_locations() -> List[Path]:
    """The real locations the manager writes to outside sandbox mode,
    resolved from the system rather than from the environment. On Linux and
    macOS these are the default XDG locations under the real home, so an
    account's own XDG overrides are not known here."""
    if os.name == "nt":
        local = _windows_folder(CSIDL_LOCAL_APPDATA) or real_home() / "AppData" / "Local"
        roaming = _windows_folder(CSIDL_APPDATA) or real_home() / "AppData" / "Roaming"
        return [local / MANAGER_ID, local / "Programs", roaming / MANAGER_ID]
    home = real_home()
    return [home / ".local" / "share" / MANAGER_ID, home / ".config" / MANAGER_ID,
            home / ".local" / "state" / MANAGER_ID, home / ".local" / "bin"]


def _inside(path: Path, root: Path) -> bool:
    """True if `path` is `root` or below it, after resolving symbolic links;
    case-insensitive where the platform's paths are."""
    target = os.path.normcase(os.path.realpath(str(path)))
    base = os.path.normcase(os.path.realpath(str(root)))
    return target == base or target.startswith(base.rstrip(os.sep) + os.sep)


def guard_path(path: Path, removing: bool = False) -> None:
    """In sandbox mode, refuse to write inside a real location the manager
    uses, or, when removing a tree, to remove one that contains such a
    location. Anywhere else, a scratch home inside the real home included,
    is allowed."""
    if not sandbox_mode():
        return
    for location in protected_locations():
        if _inside(path, location) or (removing and _inside(location, path)):
            raise ManagerError(_("sandbox mode: refusing to change {path}, which would change "
                                 "{location}, where the manager writes outside sandbox mode")
                               .format(path=path, location=location))


def check_sandbox(paths: "Paths") -> None:
    """In sandbox mode, refuse a changing command unless HOME and the XDG
    variables (LOCALAPPDATA and APPDATA for Windows) are all set, and every
    location derived from them is outside the manager's real locations."""
    if not sandbox_mode():
        return
    names = WINDOWS_SANDBOX_VARS if paths.windows else POSIX_SANDBOX_VARS
    missing = [name for name in names if not paths.environ.get(name)]
    if missing:
        raise ManagerError(_("sandbox mode: {names} must be set to a scratch directory")
                           .format(names=", ".join(missing)))
    for location in (paths.share_dir, paths.archive_dir, paths.manager_dir, paths.bin_dir,
                     paths.pointer_dir, paths.config_dir, paths.state_dir):
        guard_path(location)


# ── Small helpers ─────────────────────────────────────────────────────────────

def log(message: str) -> None:
    print(f"[{COMMAND}] {message}", file=sys.stderr)


def is_windows() -> bool:
    return platform.system() == "Windows"


def manager_version(directory: Path = _HERE) -> str:
    """This manager's version, from the VERSION file beside the script. The
    installed copy carries its own VERSION, so the file is the single source."""
    try:
        return (directory / "VERSION").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "unknown"


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
    """Pointer key suffix for an alias slot: DEFAULT, SELF or a minor line, 3.12 -> 3_12."""
    return slot if slot in (DEFAULT, SELF) else slot.replace(".", "_")


def default_alias_name(slot: str) -> str:
    if slot == DEFAULT:
        return DEFAULT_NAME
    if slot == SELF:
        return COMMAND
    return f"python{slot}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        self.environ = env
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
            # Only cmd.exe reads the pointer: every Windows alias is a .cmd file.
            self.pointer_files = {"cmd": self.pointer_dir / f"{MANAGER_ID}.env.cmd"}
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
        """(path, format) for each file that makes up alias `name`. On Windows
        that is a .cmd file only: Windows PowerShell 5.1's default execution
        policy blocks .ps1 scripts, and PowerShell prefers a .ps1 over a .cmd
        of the same name without falling back, so a .ps1 alias would stop the
        command working in PowerShell. A .cmd alias works from cmd.exe,
        PowerShell 5.1 and PowerShell 7 alike."""
        if self.windows:
            return [(self.bin_dir / f"{name}.cmd", "cmd")]
        return [(self.bin_dir / name, "posix")]

    def legacy_alias_files(self, name: str) -> List[Path]:
        """Files earlier versions wrote for alias `name` and no longer do: the
        .ps1 twin of a Windows alias, up to 1.0.2."""
        return [self.bin_dir / f"{name}.ps1"] if self.windows else []

    def runtime_dir(self, version: str) -> Path:
        return self.share_dir / version

    def archive_entry(self, version: str, build: str) -> Path:
        return self.archive_dir / f"{version}+{build}"

    def interpreter(self, root: Path) -> Path:
        """The interpreter inside a runtime directory (or a staging copy of one)."""
        if self.windows:
            return root / "python" / "python.exe"
        return root / "python" / "bin" / "python3"

    def stdlib_dir(self, root: Path, version: str) -> Path:
        if self.windows:
            return root / "python" / "Lib"
        return root / "python" / "lib" / f"python{minor_of(version)}"

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
    guard_path(path)
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if windows or not POSIX_MODES:
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
    guard_path(path)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                                    dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if not windows and POSIX_MODES:
            os.chmod(tmp_name, mode)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def make_owner_only(root: Path) -> None:
    """Owner-only permissions throughout a tree, keeping execute bits."""
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        try:
            if path.is_dir():
                path.chmod(DIR_MODE)
            else:
                executable = stat.S_IMODE(path.stat().st_mode) & 0o111
                path.chmod(EXEC_MODE if executable else FILE_MODE)
        except OSError:
            continue


def make_temp_dir(parent: Path, prefix: str) -> Path:
    """A hidden working directory beside its final location, so that moving
    the result into place is a rename on one filesystem."""
    guard_path(parent)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent)))


def remove_tree(path: Path) -> None:
    """Remove a manager-owned tree, clearing read-only flags Windows sets."""
    guard_path(path, removing=True)
    def retry(function, target, _info):
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        function(target)
    shutil.rmtree(str(path), onerror=retry)


# ── Pointer file and alias record ─────────────────────────────────────────────

# One line of each pointer syntax. Values are restricted to SAFE_VALUE_RE on
# write, so a value never needs quoting beyond the surrounding double quotes.
_POINTER_LINE = {
    "posix": re.compile(r'^(PYTHON_MANAGER_[A-Z0-9_]+)="([^"]*)"$'),
    "cmd":   re.compile(r'^set "(PYTHON_MANAGER_[A-Z0-9_]+)=([^"]*)"$', re.IGNORECASE),
}
_POINTER_COMMENT = {
    "posix": ("#",),
    "cmd":   ("rem ", "rem\t", "::"),
}
_POINTER_FORMAT = {
    "posix": ('# {line}', '{key}="{value}"'),
    "cmd":   ('rem {line}', 'set "{key}={value}"'),
}
_NEWLINE = {"posix": "\n", "cmd": "\r\n"}


class PointerRecord:
    """Which version each alias runs, and the name each alias is written under.

    `default` is the full version behind the generic alias, `lines` maps each
    minor line ("3.12") to the full version its versioned alias runs, and
    `self_version` is the manager version the manager's own alias runs.
    `aliases` maps an alias slot (DEFAULT, SELF or a minor line) to a name the
    user chose; slots without one use python, manage-python and python3.12.
    `extra` keeps PYTHON_MANAGER_* keys this version does not know, so a
    rewrite never drops what a newer manager recorded.
    """

    def __init__(self, default: Optional[str] = None,
                 lines: Optional[Dict[str, str]] = None,
                 aliases: Optional[Dict[str, str]] = None,
                 extra: Optional[Dict[str, str]] = None,
                 self_version: Optional[str] = None) -> None:
        self.default = default
        self.lines = dict(lines or {})
        self.aliases = dict(aliases or {})
        self.extra = dict(extra or {})
        self.self_version = self_version

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PointerRecord):
            return NotImplemented
        return self.to_items() == other.to_items()

    def __repr__(self) -> str:
        return f"PointerRecord({self.to_items()!r})"

    def copy(self) -> "PointerRecord":
        return copy.deepcopy(self)

    def alias_name(self, slot: str) -> str:
        return self.aliases.get(slot) or default_alias_name(slot)

    def active_slots(self) -> List[str]:
        """Slots that currently have an alias: DEFAULT, each minor line, SELF."""
        slots = [DEFAULT] if self.default else []
        slots += sorted(self.lines, key=minor_sort_key)
        return slots + ([SELF] if self.self_version else [])

    def slot_named(self, name: str) -> Optional[str]:
        """The active slot whose alias is currently called `name`."""
        for slot in self.active_slots():
            if self.alias_name(slot) == name:
                return slot
        return None

    def switch(self, version: str) -> None:
        """Point the generic alias and the version's minor line at `version`.
        The manager's own version is never changed here."""
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
        if self.self_version:
            items.append((KEY_PREFIX + SELF, self.self_version))
        alias_slots = self.active_slots()
        alias_slots += sorted((s for s in self.aliases if s not in alias_slots), key=_slot_order)
        for slot in sorted(alias_slots, key=_slot_order):
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
            elif suffix == SELF:
                record.self_version = value
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
        if self.self_version is not None:
            version_key(self.self_version)
        seen: Dict[str, str] = {}
        for slot in sorted(set(self.active_slots()) | set(self.aliases), key=_slot_order):
            name = self.alias_name(slot)
            check_alias_name(name, slot)
            # Windows and macOS filesystems are case-insensitive by default.
            folded = name.casefold()
            if folded in seen and seen[folded] != slot:
                raise ManagerError(_("alias name {name} is used twice").format(name=name))
            seen[folded] = slot


def _slot_order(slot: str) -> Tuple[int, int, int]:
    """DEFAULT first, then minor lines in numeric order, then SELF."""
    if slot == DEFAULT:
        return (0, 0, 0)
    if slot == SELF:
        return (2, 0, 0)
    return (1,) + minor_sort_key(slot)


def _slot_from_suffix(suffix: str, key: str) -> str:
    if suffix in (DEFAULT, SELF):
        return suffix
    if re.fullmatch(r"\d+_\d+", suffix):
        return suffix.replace("_", ".")
    raise ManagerError(_("unknown alias key {key}").format(key=key))


def check_alias_name(name: str, slot: Optional[str] = None) -> None:
    """Refuse a name that is not a safe file name on every platform, or that
    takes manage-python for anything but the manager's own alias."""
    if (not ALIAS_NAME_RE.match(name)
            or (slot != SELF and name.casefold() == COMMAND)
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
        _("Operator environment belongs in {env},").format(env=paths.display(paths.operator_env)),
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
                          newline=_NEWLINE[fmt], windows=paths.windows)


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
                     windows: bool = False, manager: Optional[str] = None) -> Path:
    """Write PROVENANCE into `directory`. A runtime passes version, build and
    triple; a manager version passes none of them and gets the first five keys."""
    runtime_fields = (version, build, triple)
    if any(runtime_fields) and not all(runtime_fields):
        raise ManagerError(_("a runtime's PROVENANCE needs version, build and triple together"))
    fields = {
        "manager": f"{COMMAND} {manager or manager_version()}",
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
    """Runtime directories on disk, newest first. archive/, manage-python/
    and staging directories are excluded because they are not full versions."""
    if not paths.share_dir.is_dir():
        return []
    found = [entry.name for entry in paths.share_dir.iterdir()
             if entry.is_dir() and VERSION_RE.match(entry.name)]
    return sorted(found, key=version_key, reverse=True)


def _archive_sort_key(name: str) -> Tuple[Tuple[int, int, int], int]:
    version, build = ARCHIVE_RE.match(name).groups()  # type: ignore[union-attr]
    return version_key(version), int(build)


def archived_builds(paths: Paths) -> List[str]:
    """Archive entries such as 3.12.12+20260715, newest first."""
    if not paths.archive_dir.is_dir():
        return []
    found = [entry.name for entry in paths.archive_dir.iterdir()
             if entry.is_dir() and ARCHIVE_RE.match(entry.name)]
    return sorted(found, key=_archive_sort_key, reverse=True)


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
    if record.self_version and not (paths.manager_dir / record.self_version).is_dir():
        warnings.append(_("the pointer names manager {version} for {alias}, but it is not installed")
                        .format(version=record.self_version, alias=record.alias_name(SELF)))
    for slot in record.active_slots():
        name = record.alias_name(slot)
        for alias_path, _fmt in paths.alias_files(name):
            if not alias_path.exists():
                warnings.append(_("alias {name} is recorded in the pointer, but {path} does not exist")
                                .format(name=name, path=paths.display(alias_path)))
    return lines, warnings


def manager_line(record: PointerRecord) -> str:
    """The first line of --status: the manager's alias and the version it runs."""
    return f"{record.alias_name(SELF)} {record.self_version or _('not installed')}"


def format_status(lines: List[LineStatus], manager: Optional[str] = None) -> str:
    head = f"{manager}\n\n" if manager else ""
    if not lines:
        return head + _("No Python versions installed.") + "\n"
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
    return head + "\n".join(out) + "\n"


# ── Aliases ───────────────────────────────────────────────────────────────────

ALIAS_TEMPLATES = {
    "posix": ("nix/alias.template", "#"),
    "cmd":   ("windows/alias.cmd.template", "rem"),
}
MANAGER_ALIAS_TEMPLATES = {
    "posix": ("nix/manager-alias.template", "#"),
    "cmd":   ("windows/manager-alias.cmd.template", "rem"),
}
_TOKEN_RE = re.compile(r"@[A-Z][A-Z_]*@")
OWNERSHIP_WINDOW = 4096


def templates_for(slot: str) -> Dict[str, Tuple[str, str]]:
    return MANAGER_ALIAS_TEMPLATES if slot == SELF else ALIAS_TEMPLATES


def read_template(fmt: str, templates_dir: Path = TEMPLATES_DIR, slot: str = DEFAULT) -> str:
    relpath, _comment = templates_for(slot)[fmt]
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
            ).format(path=paths.display(path), command=COMMAND, current=name))


def write_alias(paths: Paths, slot: str, name: str,
                templates_dir: Path = TEMPLATES_DIR) -> List[Path]:
    """Render and atomically write every file of one alias, after checking
    that none of them belongs to someone else."""
    check_alias_name(name, slot)
    check_alias_writable(paths, slot, name)
    # The bin directory is shared with the distribution and other tools, so
    # it is created if absent but never made owner-only.
    guard_path(paths.bin_dir)
    paths.bin_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path, fmt in paths.alias_files(name):
        _relpath, comment = templates_for(slot)[fmt]
        text = render_alias(read_template(fmt, templates_dir, slot), comment,
                            paths.display(path), KEY_PREFIX + slot_key(slot))
        atomic_write_text(path, text, newline=_NEWLINE[fmt],
                          mode=EXEC_MODE, windows=paths.windows)
        written.append(path)
    return written


def remove_alias(paths: Paths, name: str) -> List[str]:
    """Delete the files of alias `name` that this manager wrote, including
    any an earlier version wrote. Files it did not write are left in place
    and reported as warnings."""
    warnings = []
    for path in [p for p, _fmt in paths.alias_files(name)] + paths.legacy_alias_files(name):
        owner = alias_owner(path)
        if owner == "ours":
            guard_path(path)
            path.unlink()
        elif owner == "foreign":
            warnings.append(_("{path} was not written by {command}; left in place")
                            .format(path=paths.display(path), command=COMMAND))
    return warnings


ENV_PS1_NOTICE = "env-ps1-notice"          # in the state directory: the env.ps1 warning was shown


def retire_legacy_windows_files(paths: Paths) -> None:
    """Up to 1.0.2 the manager also wrote a PowerShell form of the pointer,
    python-manager.env.ps1, and its .ps1 aliases read an operator env.ps1.
    Nothing reads either now. Delete the pointer copy the manager wrote,
    recognised by its header. Leave the operator's env.ps1, which the manager
    does not own, and warn once that it is no longer read."""
    if not paths.windows:
        return
    old_pointer = paths.pointer_dir / f"{MANAGER_ID}.env.ps1"
    if old_pointer.is_file():
        try:
            head = old_pointer.read_text(encoding="utf-8", errors="replace")[:2048]
        except OSError:
            head = ""
        if f"Generated by {SCRIPT_NAME}" in head:
            guard_path(old_pointer)
            old_pointer.unlink()
            log(_("removed {path}, written by an earlier version; the pointer is now {pointer} only")
                .format(path=paths.display(old_pointer), pointer=paths.pointer_file.name))
        else:
            log(_("warning: {path} was not written by {command}; left in place")
                .format(path=paths.display(old_pointer), command=COMMAND))
    operator_ps1 = paths.config_dir / "env.ps1"
    notice = paths.state_dir / ENV_PS1_NOTICE
    if operator_ps1.is_file() and not notice.exists():
        log(_("warning: {path} is no longer read. Its settings belong in {env}, "
              "one line each: set \"NAME=value\"").format(path=paths.display(operator_ps1),
                                                       env=paths.display(paths.operator_env)))
        try:
            ensure_dir(paths.state_dir, paths.windows)
            atomic_write_text(notice, f"shown {utc_timestamp()}\n", windows=paths.windows)
        except (OSError, ManagerError):
            pass


def remove_legacy_aliases(paths: Paths, name: str) -> None:
    """Remove the files an earlier version wrote for alias `name` and this one
    no longer writes, such as a .ps1 alias on Windows, which PowerShell would
    otherwise run in place of the .cmd. A file of that name the manager did
    not write is left, with a warning that PowerShell will run it instead."""
    for path in paths.legacy_alias_files(name):
        owner = alias_owner(path)
        if owner == "ours":
            guard_path(path)
            path.unlink()
            log(_("removed {path}, written by an earlier version; {alias} replaces it")
                .format(path=paths.display(path), alias=f"{name}.cmd"))
        elif owner == "foreign":
            log(_("warning: {path} was not written by {command}; PowerShell runs it "
                  "instead of the {alias} alias").format(path=paths.display(path),
                                                         command=COMMAND, alias=name))


def write_aliases(paths: Paths, record: PointerRecord, slots: Iterable[str],
                  templates_dir: Path = TEMPLATES_DIR) -> None:
    """Write the aliases for `slots`, checking every one before writing any."""
    slots = list(slots)
    for slot in slots:
        check_alias_name(record.alias_name(slot), slot)
        check_alias_writable(paths, slot, record.alias_name(slot))
    for slot in slots:
        for path in write_alias(paths, slot, record.alias_name(slot), templates_dir):
            log(_("alias written: {path}").format(path=paths.display(path)))
        remove_legacy_aliases(paths, record.alias_name(slot))


# ── Release lookup ────────────────────────────────────────────────────────────

class Build:
    """One python-build-standalone runtime for one platform."""

    def __init__(self, version: str, build: str, triple: str) -> None:
        version_key(version)
        if not build.isdigit():
            raise ManagerError(_("not a build tag: {build!r}").format(build=build))
        self.version, self.build, self.triple = version, build, triple

    def __repr__(self) -> str:
        return f"Build({self.version}+{self.build}, {self.triple})"

    @property
    def asset(self) -> str:
        return f"cpython-{self.version}+{self.build}-{self.triple}-{FLAVOR}.tar.gz"

    @property
    def url(self) -> str:
        return f"{DOWNLOAD_BASE}/{self.build}/{self.asset}"

    @property
    def sums_url(self) -> str:
        return f"{DOWNLOAD_BASE}/{self.build}/SHA256SUMS"

    @property
    def label(self) -> str:
        return f"{self.version}+{self.build}"


class Network:
    """The manager's only contact with the outside world, so tests can
    replace it. A GITHUB_TOKEN in the environment is sent to the GitHub API
    only, never to download hosts, for a higher rate limit."""

    def __init__(self, environ: Optional[Mapping[str, str]] = None) -> None:
        env = os.environ if environ is None else environ
        self.token = env.get("GITHUB_TOKEN") or ""
        self.user_agent = f"{PROJECT}/{manager_version()}"

    def _open(self, url: str, timeout: int):
        headers = {"User-Agent": self.user_agent}
        if url.startswith("https://api.github.com/"):
            headers["Accept"] = "application/vnd.github+json"
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code == 403 and "api.github.com" in url:
                raise ManagerError(_(
                    "GitHub API rate limit reached. Wait and retry, set GITHUB_TOKEN, "
                    "or install a pinned build such as 3.12.14+20260924, which needs no API call"
                )) from None
            raise ManagerError(_("download failed ({code}) for {url}")
                               .format(code=error.code, url=url)) from None
        except (urllib.error.URLError, OSError) as error:
            raise ManagerError(_("network error for {url}: {error}")
                               .format(url=url, error=error)) from None

    def get_json(self, url: str):
        with self._open(url, 30) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_text(self, url: str) -> str:
        with self._open(url, 60) as response:
            return response.read().decode("utf-8")

    def download(self, url: str, destination: Path) -> None:
        with self._open(url, 120) as response, open(destination, "wb") as out:
            shutil.copyfileobj(response, out)


def parse_spec(spec: str) -> Tuple[str, str]:
    """Classify an --install SPEC: ("track", ""), ("minor", "3.13"),
    ("version", "3.12.14") or ("pinned", "3.12.14+20260924")."""
    if spec == "":
        return "track", ""
    if MINOR_RE.match(spec):
        return "minor", spec
    if VERSION_RE.match(spec):
        return "version", spec
    if ARCHIVE_RE.match(spec):
        return "pinned", spec
    raise UsageError(_(
        "{spec!r} is not a minor line (3.13), a version (3.12.14) or a build (3.12.14+20260924)"
    ).format(spec=spec))


_ASSET_RE = re.compile(r"^cpython-(\d+\.\d+\.\d+)((?:a|b|rc)\d+)?\+(\d+)-(.+)\.tar\.gz$")


def excluded_build(name: str) -> Optional[str]:
    """Why a release asset is never installed, or None if it may be:
    pre-releases (alpha, beta, rc) and free-threaded builds are excluded
    everywhere, whatever the rest of the name says."""
    if "freethreaded" in name:
        return "free-threaded"
    match = _ASSET_RE.match(name)
    if match and match.group(2):
        return "pre-release"
    return None


def builds_in_release(release: Mapping, triple: str) -> List[Build]:
    """Every selectable install_only_stripped build for `triple` in a release,
    newest first. Variant triples such as x86_64_v3 never match."""
    found = []
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        match = _ASSET_RE.match(name)
        if not match or excluded_build(name):
            continue
        version, _prerelease, build, rest = match.groups()
        if rest != f"{triple}-{FLAVOR}":
            continue
        found.append(Build(version, build, triple))
    return sorted(found, key=lambda b: (version_key(b.version), int(b.build)), reverse=True)


def archived_build(paths: Paths, version: str, triple: str) -> Optional[Build]:
    """The newest archived build of `version`, if any."""
    for name in archived_builds(paths):
        archived_version, build = ARCHIVE_RE.match(name).groups()  # type: ignore[union-attr]
        if archived_version == version:
            return Build(version, build, triple)
    return None


def resolve(kind: str, value: str, triple: str, paths: Paths, net: Network,
            track: Optional[str]) -> Build:
    """Turn an --install SPEC into one build. Pinned builds and versions
    already in the archive need no network; a minor line needs the latest
    release; a version not in the archive searches recent releases. With no
    SPEC, `track` is the current default's minor line, or None on a first
    install, which takes the newest stable minor line in the latest release."""
    if kind == "pinned":
        version, build = ARCHIVE_RE.match(value).groups()  # type: ignore[union-attr]
        return Build(version, build, triple)
    if kind == "version":
        archived = archived_build(paths, value, triple)
        if archived:
            return archived
        for page in range(1, RELEASE_PAGES + 1):
            releases = net.get_json(f"{API_BASE}/releases?per_page=30&page={page}")
            for release in releases:
                for build in builds_in_release(release, triple):
                    if build.version == value:
                        return build
            if len(releases) < 30:
                break
        raise ManagerError(_(
            "no recent python-build-standalone release has CPython {version} for {triple}"
        ).format(version=value, triple=triple))
    minor = value or track
    release = net.get_json(f"{API_BASE}/releases/latest")
    builds = [b for b in builds_in_release(release, triple)
              if minor is None or minor_of(b.version) == minor]
    if not builds:
        raise ManagerError(_(
            "python-build-standalone release {tag} has no stable CPython {minor} for {triple} "
            "(pre-release and free-threaded builds are not installed)"
        ).format(tag=release.get("tag_name", "?"), minor=minor or "", triple=triple))
    return builds[0]


def parse_sha256sums(text: str) -> Dict[str, str]:
    checksums = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and not parts[0].startswith("#"):
            checksums[parts[1].lstrip("*")] = parts[0].lower()
    return checksums


# ── Acquisition and extraction ────────────────────────────────────────────────

def acquire(build: Build, paths: Paths, net: Network, workdir: Path) -> Tuple[Path, str, str, bool]:
    """Archive-first: the verified tarball for `build`, as (path, sha256,
    source, from_archive). An archived tarball is checked against the
    checksum recorded beside it; a download against the release's SHA256SUMS."""
    entry = paths.archive_entry(build.version, build.build)
    archived = entry / build.asset
    if archived.is_file():
        recorded = read_provenance(entry).get("sha256", "")
        actual = sha256_of(archived)
        if actual != recorded:
            raise ManagerError(_(
                "archived {asset} does not match its recorded checksum; "
                "not installing it. Move {entry} aside to download it again"
            ).format(asset=build.asset, entry=paths.display(entry)))
        log(_("using the archived {label}, verified").format(label=build.label))
        return archived, actual, f"local archive ({paths.display(archived)})", True

    log(_("downloading SHA256SUMS for release {build}...").format(build=build.build))
    expected = parse_sha256sums(net.get_text(build.sums_url)).get(build.asset)
    if not expected:
        raise ManagerError(_("{asset} is not listed in SHA256SUMS for release {build}; "
                             "refusing to install unverified")
                           .format(asset=build.asset, build=build.build))
    target = workdir / build.asset
    log(_("downloading {asset}...").format(asset=build.asset))
    net.download(build.url, target)
    actual = sha256_of(target)
    if actual != expected:
        raise ManagerError(_("checksum mismatch for {asset}: expected {expected}, got {actual}")
                           .format(asset=build.asset, expected=expected, actual=actual))
    log(_("verified SHA-256"))
    return target, actual, build.url, False


def _check_member(member: tarfile.TarInfo, destination: Path) -> None:
    """The safety rules of tarfile's data filter, for Pythons that predate it."""
    name = PurePosixPath(member.name)
    if name.is_absolute() or ".." in name.parts:
        raise ManagerError(_("refusing unsafe path in archive: {name}").format(name=member.name))
    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
        raise ManagerError(_("refusing special file in archive: {name}").format(name=member.name))
    if member.issym() or member.islnk():
        base = destination / name.parent if member.issym() else destination
        target = os.path.normpath(str(base / member.linkname))
        if (PurePosixPath(member.linkname).is_absolute()
                or not target.startswith(str(destination) + os.sep)):
            raise ManagerError(_("refusing link that leaves the archive: {name}")
                               .format(name=member.name))


def extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        if hasattr(tarfile, "data_filter"):
            try:
                tar.extractall(destination, filter="data")
            except tarfile.FilterError as error:
                raise ManagerError(_("refusing unsafe archive {asset}: {error}")
                                   .format(asset=archive.name, error=error)) from None
            return
        members = tar.getmembers()
        for member in members:
            _check_member(member, destination.resolve())
        tar.extractall(destination, members=members)


def health_check(interpreter: Path, version: str) -> None:
    """Refuse a runtime unless its python starts and reports `version`."""
    probe = "import sys; print('%d.%d.%d' % sys.version_info[:3])"
    try:
        result = subprocess.run([str(interpreter), "-c", probe],
                                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise ManagerError(_(
            "the runtime did not start: {error}. On NixOS, enable nix-ld "
            "(programs.nix-ld.enable = true)"
        ).format(error=error)) from None
    reported = result.stdout.strip()
    if result.returncode != 0 or reported != version:
        raise ManagerError(_("the runtime failed its health check: expected {version}, got {reported!r}")
                           .format(version=version, reported=reported or result.stderr.strip()))


# pip reads this file with configparser, which strips the leading space of
# continuation lines and ends the value at a blank line, so the message has
# no spacer or indented lines: each line is printed as written here.
EXTERNALLY_MANAGED = """[externally-managed]
Error=This Python runtime is managed by manage-python and does not accept
 package installs, so it stays intact for every virtual environment built on it.
 Create a virtual environment and install into that instead, for example:
 python{minor} -m venv .venv
"""


def write_externally_managed(stdlib: Path, version: str, windows: bool) -> None:
    if not stdlib.is_dir():
        raise ManagerError(_("standard library directory not found in the runtime: {path}")
                           .format(path=stdlib))
    atomic_write_text(stdlib / "EXTERNALLY-MANAGED",
                      EXTERNALLY_MANAGED.format(minor=minor_of(version)), windows=windows)


def install_runtime(build: Build, tarball: Path, sha256: str, source: str,
                    paths: Paths, now: Optional[datetime] = None,
                    manager: Optional[str] = None) -> None:
    """Extract, health-check, protect and record a runtime in a staging
    directory, then rename it into place, so a failed install leaves nothing."""
    staging = make_temp_dir(paths.share_dir, f".staging-{build.version}-")
    try:
        extract(tarball, staging)
        health_check(paths.interpreter(staging), build.version)
        write_externally_managed(paths.stdlib_dir(staging, build.version), build.version,
                                 paths.windows)
        write_provenance(staging, asset=build.asset, sha256=sha256, source=source,
                         version=build.version, build=build.build, triple=build.triple,
                         now=now, windows=paths.windows, manager=manager)
        if not paths.windows and POSIX_MODES:
            make_owner_only(staging)
        os.rename(str(staging), str(paths.runtime_dir(build.version)))
    except BaseException:
        if staging.exists():
            remove_tree(staging)
        raise


def archive_tarball(build: Build, tarball: Path, sha256: str, source: str,
                    paths: Paths, now: Optional[datetime] = None,
                    manager: Optional[str] = None) -> None:
    """Keep a verified tarball, with a PROVENANCE recording its checksum."""
    ensure_dir(paths.archive_dir, paths.windows)
    entry = paths.archive_entry(build.version, build.build)
    staging = make_temp_dir(paths.archive_dir, f".staging-{build.label}-")
    try:
        shutil.copyfile(str(tarball), str(staging / build.asset))
        write_provenance(staging, asset=build.asset, sha256=sha256, source=source,
                         version=build.version, build=build.build, triple=build.triple,
                         now=now, windows=paths.windows, manager=manager)
        if not paths.windows and POSIX_MODES:
            make_owner_only(staging)
        if entry.exists():
            remove_tree(entry)
        os.rename(str(staging), str(entry))
    except BaseException:
        if staging.exists():
            remove_tree(staging)
        raise


# ── The manager itself ────────────────────────────────────────────────────────

# What an installed manager version needs beside the script to run and render aliases.
SELF_FILES = ["VERSION"] + [f"scripts/{relpath}" for relpath, _c in
                            list(ALIAS_TEMPLATES.values()) + list(MANAGER_ALIAS_TEMPLATES.values())]


def install_self(paths: Paths, source_dir: Path = _HERE,
                 now: Optional[datetime] = None) -> str:
    """Install this manager under manage-python/<version>/, unless that
    version is already there, and return the version."""
    version = manager_version(source_dir)
    if not VERSION_RE.match(version):
        raise ManagerError(_("{path} does not hold a version ({version!r}); cannot install the manager")
                           .format(path=source_dir / "VERSION", version=version))
    target = paths.manager_dir / version
    if target.is_dir():
        return version
    ensure_dir(paths.manager_dir, paths.windows)
    staging = make_temp_dir(paths.manager_dir, f".staging-{version}-")
    try:
        for relpath in [SCRIPT_NAME] + SELF_FILES:
            destination = staging / relpath
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source_dir / relpath), str(destination))
        locale = source_dir / "locale"
        if locale.is_dir():
            shutil.copytree(str(locale), str(staging / "locale"))
        script = source_dir / SCRIPT_NAME
        write_provenance(staging, asset=SCRIPT_NAME, sha256=sha256_of(script),
                         source=f"local copy ({paths.display(script)})", now=now,
                         windows=paths.windows, manager=version)
        if not paths.windows and POSIX_MODES:
            make_owner_only(staging)
        os.rename(str(staging), str(target))
    except BaseException:
        if staging.exists():
            remove_tree(staging)
        raise
    log(_("manager {version} installed: {path}").format(version=version,
                                                        path=paths.display(target)))
    return version


# ── Operator log ──────────────────────────────────────────────────────────────

def append_log(paths: Paths, action: str, target: str, result: str,
               now: Optional[datetime] = None) -> None:
    """One line per lifecycle action: time, action, version, result."""
    try:
        ensure_dir(paths.state_dir, paths.windows)
        guard_path(paths.log_file)
        line = " ".join([utc_timestamp(now), action, target or "-",
                         " ".join(result.split())])
        with open(paths.log_file, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        if not paths.windows and POSIX_MODES:
            paths.log_file.chmod(FILE_MODE)
    except (OSError, ManagerError) as error:
        log(_("warning: could not write {path}: {error}")
            .format(path=paths.display(paths.log_file), error=error))


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status(paths: Paths) -> int:
    record = read_pointer(paths)
    lines, warnings = collect_status(paths, record)
    sys.stdout.write(format_status(lines, manager_line(record)))
    for warning in warnings:
        log(_("warning: {message}").format(message=warning))
    return 0


def cmd_install(spec: str, paths: Paths, net: Network, triple: Optional[str] = None,
                source_dir: Path = _HERE, templates_dir: Path = TEMPLATES_DIR,
                now: Optional[datetime] = None) -> str:
    """Install a runtime and switch to it; install the manager itself on first
    use. Aliases are checked before any network access. Returns the version."""
    check_sandbox(paths)
    kind, value = parse_spec(spec)
    record = read_pointer(paths)
    track = minor_of(record.default) if record.default else None
    if kind == "track":
        minor = track
    elif kind == "minor":
        minor = value
    else:
        minor = minor_of(value.split("+")[0])

    plan = record.copy()
    install_manager = not (plan.self_version and (paths.manager_dir / plan.self_version).is_dir())
    # Every alias this install will write, checked before any network access.
    # Only a first install with no SPEC learns its minor line from the release.
    slots = [DEFAULT, SELF] + ([minor] if minor else []) + [
        s for s in plan.active_slots() if s not in (DEFAULT, SELF, minor)]
    for slot in slots:
        check_alias_name(plan.alias_name(slot), slot)
        check_alias_writable(paths, slot, plan.alias_name(slot))

    triple = triple or detect_triple()
    build = resolve(kind, value, triple, paths, net, track)
    log(_("selected CPython {label} ({triple})").format(label=build.label, triple=triple))
    if minor is None:
        minor = minor_of(build.version)
        check_alias_name(plan.alias_name(minor), minor)
        check_alias_writable(paths, minor, plan.alias_name(minor))

    ensure_dir(paths.share_dir, paths.windows)
    if paths.runtime_dir(build.version).is_dir():
        log(_("{version} is already installed").format(version=build.version))
    else:
        workdir = make_temp_dir(paths.share_dir, ".download-")
        try:
            tarball, sha256, source, from_archive = acquire(build, paths, net, workdir)
            log(_("installing to {path}...").format(path=paths.display(paths.runtime_dir(build.version))))
            running = manager_version(source_dir)
            install_runtime(build, tarball, sha256, source, paths, now, running)
            if not from_archive:
                archive_tarball(build, tarball, sha256, source, paths, now, running)
        finally:
            remove_tree(workdir)

    if install_manager:
        plan.self_version = install_self(paths, source_dir, now)
    elif plan.self_version != manager_version(source_dir):
        log(_("manager {installed} stays in use; this is {running}. Self-update is not yet available")
            .format(installed=plan.self_version, running=manager_version(source_dir)))
    plan.switch(build.version)
    write_pointer(plan, paths)
    write_aliases(paths, plan, plan.active_slots(), templates_dir)
    log(_("CPython {version} installed; python and {alias} now run it")
        .format(version=build.version, alias=plan.alias_name(minor)))
    retire_legacy_windows_files(paths)
    if paths.windows:
        add_to_windows_user_path(paths, now=now)
    path_notes(paths)
    return build.version


# ── Windows user PATH ─────────────────────────────────────────────────────────

WINDOWS_BIN_ENTRY = r"%LOCALAPPDATA%\Programs"
REG_SZ, REG_EXPAND_SZ = 1, 2                    # winreg's value types, for tests off Windows


def expand_windows_vars(text: str, environ: Mapping[str, str]) -> str:
    """%NAME% expansion as Windows does it: case-insensitive, unknown names kept."""
    folded = {key.upper(): value for key, value in environ.items()}
    return re.sub(r"%([^%;]+)%", lambda m: folded.get(m.group(1).upper(), m.group(0)), text)


def _path_key(entry: str, environ: Mapping[str, str]) -> str:
    expanded = expand_windows_vars(entry.strip().strip('"'), environ)
    return expanded.replace("/", "\\").rstrip("\\").casefold()


def prepend_path_entry(current: str, value_type: int, environ: Mapping[str, str]) -> Optional[str]:
    """The user Path with %LOCALAPPDATA%\\Programs first, or None if it is
    already there in any spelling. A REG_EXPAND_SZ value gets the entry
    unexpanded; a REG_SZ value cannot expand it, so it gets the expanded path."""
    target = _path_key(WINDOWS_BIN_ENTRY, environ)
    entries = [e for e in current.split(";") if e.strip()]
    if any(_path_key(e, environ) == target for e in entries):
        return None
    entry = WINDOWS_BIN_ENTRY if value_type == REG_EXPAND_SZ else \
        expand_windows_vars(WINDOWS_BIN_ENTRY, environ)
    return ";".join([entry] + entries)


def _broadcast_environment_change() -> None:
    """Tell Explorer and other top-level windows that the environment changed,
    so terminals opened afterwards see the new Path."""
    import ctypes
    from ctypes import wintypes
    result = wintypes.DWORD()
    ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
        0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(result))


REG_TYPE_NAMES = {REG_SZ: "REG_SZ", REG_EXPAND_SZ: "REG_EXPAND_SZ"}


def write_path_backup(paths: Paths, previous: Optional[str], value_type: int,
                      now: Optional[datetime] = None) -> Path:
    """Save the user Path as it was, with its registry type, before the
    manager changes it: path-backup-<UTC>.txt in the state directory."""
    ensure_dir(paths.state_dir, paths.windows)
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    backup = paths.state_dir / f"path-backup-{moment.strftime('%Y%m%dT%H%M%SZ')}.txt"
    text = (f"# HKCU\\Environment\\Path before {COMMAND} prepended {WINDOWS_BIN_ENTRY}\n"
            f"saved: {utc_timestamp(moment)}\n"
            f"type: {REG_TYPE_NAMES[value_type] if previous is not None else 'absent'}\n"
            f"value: {previous or ''}\n")
    atomic_write_text(backup, text, newline=_NEWLINE["cmd" if paths.windows else "posix"],
                      windows=paths.windows)
    return backup


def add_to_windows_user_path(paths: Paths, registry=None,
                             broadcast: Optional[Callable[[], None]] = None,
                             now: Optional[datetime] = None) -> bool:
    """Prepend %LOCALAPPDATA%\\Programs to HKCU\\Environment Path, keeping its
    value type, unless it is already there. A change is visible and
    reversible: the previous value is backed up first, the change is
    announced with how to undo it, and it is logged as a "path" action.
    When the entry is already present nothing is printed or logged. A failure
    is logged and reported but does not fail the install. Returns True if
    Path changed."""
    if sandbox_mode():
        log(_("sandbox mode: the Windows user PATH is not changed"))
        return False
    if registry is None:
        import winreg as registry  # type: ignore[import-not-found,no-redef]
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, "Environment", 0,
                              registry.KEY_READ | registry.KEY_WRITE) as key:
            try:
                current, value_type = registry.QueryValueEx(key, "Path")
                previous: Optional[str] = current
            except FileNotFoundError:
                current, value_type, previous = "", registry.REG_EXPAND_SZ, None
            if value_type not in (registry.REG_SZ, registry.REG_EXPAND_SZ):
                raise ManagerError(_("HKCU\\Environment\\Path has an unexpected registry type"))
            updated = prepend_path_entry(current, value_type, paths.environ)
            if updated is None:
                return False
            backup = write_path_backup(paths, previous, value_type, now)
            registry.SetValueEx(key, "Path", 0, value_type, updated)
    except (OSError, ManagerError) as error:
        append_log(paths, "path", WINDOWS_BIN_ENTRY, f"failed: {error}", now)
        log(_("warning: your user PATH was not changed: {error}. Add {entry} to it "
              "yourself to run the manager's commands from any terminal")
            .format(error=error, entry=WINDOWS_BIN_ENTRY))
        return False
    try:
        (broadcast or _broadcast_environment_change)()
    except (OSError, AttributeError) as error:
        log(_("warning: could not tell Windows the environment changed ({error}); "
              "sign out and in again if new terminals do not see it").format(error=error))
    shown = paths.display(backup)
    log(_("Added {entry} to the start of your user PATH (HKCU\\Environment\\Path) so the "
          "manager's commands are found. Open a new terminal to use them.")
        .format(entry=WINDOWS_BIN_ENTRY))
    log(_("Your previous PATH was saved to {backup}. To undo, run: "
          "rundll32 sysdm.cpl,EditEnvironmentVariables  then select Path under your "
          "user variables and remove that entry.").format(backup=shown))
    append_log(paths, "path", WINDOWS_BIN_ENTRY, f"ok: prepended to user PATH, backup {shown}", now)
    return True


def path_notes(paths: Paths) -> None:
    entries = [Path(p) for p in paths.environ.get("PATH", "").split(os.pathsep) if p]
    if paths.bin_dir in entries or paths.windows:
        return
    if platform.system() == "Darwin":
        log(_("{path} is not on your PATH. Add this line to ~/.zshrc and open a new terminal:\n"
              "    export PATH=\"$HOME/.local/bin:$PATH\"").format(path=paths.display(paths.bin_dir)))
    else:
        log(_("{path} is not on your PATH yet. Log in again, or run: . ~/.profile")
            .format(path=paths.display(paths.bin_dir)))


def cmd_switch(version: str, paths: Paths, templates_dir: Path = TEMPLATES_DIR) -> str:
    check_sandbox(paths)
    if not VERSION_RE.match(version):
        raise UsageError(_("--switch takes a full version such as 3.12.14, not {version!r}")
                         .format(version=version))
    if not paths.runtime_dir(version).is_dir():
        raise ManagerError(_("{version} is not installed; install it with: {command} --install {version}")
                           .format(version=version, command=COMMAND))
    record = read_pointer(paths).copy()
    record.switch(version)
    slots = [DEFAULT, minor_of(version)]
    for slot in slots:
        check_alias_writable(paths, slot, record.alias_name(slot))
    write_pointer(record, paths)
    write_aliases(paths, record, slots, templates_dir)
    retire_legacy_windows_files(paths)
    log(_("python and {alias} now run {version}")
        .format(alias=record.alias_name(minor_of(version)), version=version))
    return version


def cmd_remove(version: str, paths: Paths) -> str:
    check_sandbox(paths)
    if not VERSION_RE.match(version):
        raise UsageError(_("--remove takes a full version such as 3.12.13, not {version!r}")
                         .format(version=version))
    runtime = paths.runtime_dir(version)
    if not runtime.is_dir():
        raise ManagerError(_("{version} is not installed").format(version=version))
    record = read_pointer(paths).copy()
    minor = minor_of(version)
    if record.default == version:
        raise ManagerError(_("{version} is the default version, which {alias} and the manager "
                             "run on. Switch to another version first")
                           .format(version=version, alias=record.alias_name(DEFAULT)))
    stale_alias = None
    if record.lines.get(minor) == version:
        others = [v for v in installed_versions(paths) if minor_of(v) == minor and v != version]
        if others:
            raise ManagerError(_(
                "{alias} runs {version}. Point it at {other} first with "
                "--switch {other}, then --switch {default} to move python back"
            ).format(alias=record.alias_name(minor), version=version, other=others[0],
                     default=record.default))
        # The last version of its line: the line's alias goes with it. A
        # renamed alias keeps its name in the pointer for a later install.
        stale_alias = record.alias_name(minor)
        del record.lines[minor]
        write_pointer(record, paths)
        for warning in remove_alias(paths, stale_alias):
            log(_("warning: {message}").format(message=warning))
    log(_("virtual environments created with {version} stop working until it is reinstalled")
        .format(version=version))
    trash = make_temp_dir(paths.share_dir, f".removing-{version}-")
    os.rename(str(runtime), str(trash / version))
    remove_tree(trash)
    log(_("{version} removed").format(version=version)
        + (_("; alias {alias} removed with it").format(alias=stale_alias) if stale_alias else ""))
    retire_legacy_windows_files(paths)
    archived = archived_build(paths, version, "")
    if archived:
        log(_("its verified tarball remains in the archive; reinstall offline with: "
              "{command} --install {label}").format(command=COMMAND, label=archived.label))
    return version


def cmd_alias(spec: str, paths: Paths, templates_dir: Path = TEMPLATES_DIR) -> str:
    """Rename an alias. OLD is its current name, or, for an alias not yet
    written, its default name, so a collision can be avoided before an install."""
    check_sandbox(paths)
    old, sep, new = spec.partition("=")
    if not sep or not old or not new:
        raise UsageError(_("--alias takes OLD=NEW, for example python3.12=py312"))
    record = read_pointer(paths)
    slot = record.slot_named(old)
    if slot is None:
        defaults = {DEFAULT_NAME: DEFAULT, COMMAND: SELF}
        match = re.fullmatch(r"python(\d+\.\d+)", old)
        slot = defaults.get(old) or (match.group(1) if match else None)
        if slot is None or slot in record.active_slots():
            raise ManagerError(_("there is no alias named {name}").format(name=old))
    if record.alias_name(slot) == new:
        log(_("{name} is already called {name}").format(name=new))
        return new
    updated = record.copy()
    updated.aliases[slot] = new
    updated.validate()
    active = slot in updated.active_slots()
    if active:
        check_alias_writable(paths, slot, new)
    write_pointer(updated, paths)
    if active:
        write_aliases(paths, updated, [slot], templates_dir)
        for warning in remove_alias(paths, record.alias_name(slot)):
            log(_("warning: {message}").format(message=warning))
    retire_legacy_windows_files(paths)
    log(_("{old} is now {new}").format(old=record.alias_name(slot), new=new))
    return new


def root_guard() -> None:
    """Refuse to change anything as root or Administrator: everything this
    manager writes belongs to the invoking user."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise ManagerError(_("this manager writes to your home directory; do not run it with sudo"))
    if os.name == "nt":
        try:
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin():  # type: ignore[attr-defined]
                raise ManagerError(_("this manager writes to your profile; do not run it as Administrator"))
        except (AttributeError, OSError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog=COMMAND,
        description=_("Manage user-space installations of CPython."),
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--install", nargs="?", const="", metavar="SPEC",
                         help=_("Install and switch to a runtime: 3.13, 3.12.14 or 3.12.14+20260924 "
                                "(default: latest of the default's minor line, or the newest "
                                "stable minor line on a first install)."))
    actions.add_argument("--switch", metavar="VERSION",
                         help=_("Make an installed version the one python and its minor alias run."))
    actions.add_argument("--status", action="store_true",
                         help=_("Show aliases, default, installed and archived versions."))
    actions.add_argument("--remove", metavar="VERSION",
                         help=_("Remove an installed version no alias needs; the archive is kept."))
    actions.add_argument("--alias", metavar="OLD=NEW",
                         help=_("Rename an alias, for example python3.12=py312."))
    actions.add_argument("--version", action="store_true",
                         help=_("Show this manager's version and exit."))
    parser.add_argument("--lang", metavar="LANG",
                        help=_("Language for this command's messages, for example fr."))
    args = parser.parse_args(argv)

    try:
        lang, warning = choose_lang(args.lang, os.environ)
    except UsageError as error:
        log(_("ERROR: {message}").format(message=error))
        return 2
    set_language(lang)
    if warning:
        log(_("warning: {message}").format(message=warning))

    if args.version:
        print(f"{COMMAND} {manager_version()}")
        return 0
    if args.status:
        try:
            return cmd_status(Paths())
        except ManagerError as error:
            log(_("ERROR: {message}").format(message=error))
            return 1

    lifecycle = [("install", args.install, lambda p: cmd_install(args.install, p, Network())),
                 ("switch", args.switch, lambda p: cmd_switch(args.switch, p)),
                 ("remove", args.remove, lambda p: cmd_remove(args.remove, p)),
                 ("alias", args.alias, lambda p: cmd_alias(args.alias, p))]
    for action, value, run in lifecycle:
        if value is None:
            continue
        paths = Paths()
        try:
            root_guard()
            result = run(paths)
        except UsageError as error:
            log(_("ERROR: {message}").format(message=error))
            return 2                                # not an action, so not logged
        except ManagerError as error:
            log(_("ERROR: {message}").format(message=error))
            append_log(paths, action, value, f"failed: {error}")
            return 1
        append_log(paths, action, result, "ok")
        return 0
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
