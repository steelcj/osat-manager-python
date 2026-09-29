#!/usr/bin/env python3
# test_manage_python.py
"""
test_manage_python.py, offline unit tests for manage-python.py.

Covers the parts that need no downloads: the pointer file and alias record,
PROVENANCE, platform triple selection, status output, and alias rendering
with its ownership check. Every test works in a scratch directory; nothing
touches the real home directory or the network.

Usage:
    python3 -m unittest test_manage_python -v
"""

import hashlib
import importlib.util
import io
import os
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent / "manage-python.py"
_spec = importlib.util.spec_from_file_location("manage_python", _SCRIPT)
mp = importlib.util.module_from_spec(_spec)
sys.modules["manage_python"] = mp
_spec.loader.exec_module(mp)

POSIX_ONLY = unittest.skipIf(os.name == "nt", "exercises POSIX modes and /bin/sh")

# The pointer as the proposal's pointer file section shows it.
PROPOSAL_POINTER = '''PYTHON_MANAGER_DEFAULT="3.12.14"
PYTHON_MANAGER_3_12="3.12.14"
PYTHON_MANAGER_3_13="3.13.15"

PYTHON_MANAGER_ALIAS_DEFAULT="python"
PYTHON_MANAGER_ALIAS_3_12="py312"
PYTHON_MANAGER_ALIAS_3_13="python3.13"
'''

# PROVENANCE exactly as install-restic.py 0.4.4 writes it.
RESTIC_PROVENANCE = (
    "manager: osat-fluent-restic-tool 0.4.4\n"
    "asset: restic_0.19.1_linux_amd64.bz2\n"
    "sha256: " + "ab" * 32 + "\n"
    "source: https://github.com/restic/restic/releases/download/v0.19.1/restic_0.19.1_linux_amd64.bz2\n"
    "installed: 2026-08-11T09:15:02Z\n"
)


class Scratch(unittest.TestCase):
    """A scratch home with Paths resolved inside it, for either platform."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="manage-python-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def posix_paths(self, **env):
        return mp.Paths(windows=False, environ=env, home=self.home)

    def windows_paths(self):
        env = {"LOCALAPPDATA": str(self.home / "AppData" / "Local"),
               "APPDATA": str(self.home / "AppData" / "Roaming")}
        return mp.Paths(windows=True, environ=env, home=self.home)

    def make_runtime(self, paths, version):
        (paths.runtime_dir(version) / "python" / "bin").mkdir(parents=True)

    def make_archive(self, paths, build):
        (paths.archive_dir / build).mkdir(parents=True)


# ── Paths ─────────────────────────────────────────────────────────────────────

class TestPaths(Scratch):

    def test_posix_defaults(self):
        paths = self.posix_paths()
        self.assertEqual(paths.share_dir, self.home / ".local/share/python-manager")
        self.assertEqual(paths.bin_dir, self.home / ".local/bin")
        self.assertEqual(paths.pointer_file, self.home / ".config/python-manager/python-manager.env")
        self.assertEqual(paths.operator_env, self.home / ".config/python-manager/env")
        self.assertEqual(paths.state_dir, self.home / ".local/state/python-manager")
        self.assertEqual(paths.manager_dir, paths.share_dir / "manage-python")

    def test_posix_respects_xdg(self):
        paths = self.posix_paths(XDG_DATA_HOME=str(self.tmp / "d"),
                                 XDG_CONFIG_HOME=str(self.tmp / "c"),
                                 XDG_STATE_HOME=str(self.tmp / "s"),
                                 XDG_BIN_HOME=str(self.tmp / "b"))
        self.assertEqual(paths.share_dir, self.tmp / "d/python-manager")
        self.assertEqual(paths.pointer_file, self.tmp / "c/python-manager/python-manager.env")
        self.assertEqual(paths.state_dir, self.tmp / "s/python-manager")
        self.assertEqual(paths.bin_dir, self.tmp / "b")

    def test_windows_pointer_is_local_not_roaming(self):
        paths = self.windows_paths()
        local = self.home / "AppData" / "Local"
        self.assertEqual(paths.pointer_files, {
            "cmd": local / "python-manager" / "python-manager.env.cmd",
            "ps1": local / "python-manager" / "python-manager.env.ps1"})
        self.assertEqual(paths.operator_env,
                         self.home / "AppData" / "Roaming" / "python-manager" / "env.cmd")
        self.assertEqual(paths.bin_dir, local / "Programs")
        self.assertEqual(paths.state_dir, local / "python-manager" / "logs")

    def test_alias_files_per_platform(self):
        self.assertEqual([f for _, f in self.posix_paths().alias_files("python")], ["posix"])
        self.assertEqual([p.name for p, _ in self.windows_paths().alias_files("python3.12")],
                         ["python3.12.cmd", "python3.12.ps1"])

    def test_display(self):
        self.assertEqual(self.posix_paths().display(self.home / ".local/bin/python3.12"),
                         "~/.local/bin/python3.12")
        paths = self.windows_paths()
        self.assertTrue(paths.display(paths.bin_dir / "python.cmd").startswith("%LOCALAPPDATA%"))
        self.assertEqual(paths.display(Path("/elsewhere")), "/elsewhere")


# ── Pointer file and alias record ─────────────────────────────────────────────

class TestPointerRecord(unittest.TestCase):

    def test_default_alias_names(self):
        record = mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"})
        self.assertEqual(record.alias_name(mp.DEFAULT), "python")
        self.assertEqual(record.alias_name("3.12"), "python3.12")

    def test_switch_moves_default_and_its_line_only(self):
        record = mp.PointerRecord(default="3.12.14",
                                  lines={"3.12": "3.12.14", "3.13": "3.13.15"})
        record.switch("3.12.13")
        self.assertEqual(record.default, "3.12.13")
        self.assertEqual(record.lines, {"3.12": "3.12.13", "3.13": "3.13.15"})
        record.switch("3.13.15")
        self.assertEqual(record.lines["3.12"], "3.12.13")
        record.validate()

    def test_rename_survives_switch(self):
        record = mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"},
                                  aliases={"3.12": "py312"})
        record.switch("3.12.13")
        self.assertEqual(record.alias_name("3.12"), "py312")

    def test_items_order_matches_proposal(self):
        record = mp.PointerRecord(default="3.12.14",
                                  lines={"3.13": "3.13.15", "3.12": "3.12.14"},
                                  aliases={"3.12": "py312"})
        self.assertEqual([k for k, _ in record.to_items()], [
            "PYTHON_MANAGER_DEFAULT", "PYTHON_MANAGER_3_12", "PYTHON_MANAGER_3_13",
            "PYTHON_MANAGER_ALIAS_DEFAULT", "PYTHON_MANAGER_ALIAS_3_12",
            "PYTHON_MANAGER_ALIAS_3_13"])

    def test_minor_lines_sort_numerically(self):
        record = mp.PointerRecord(lines={"3.9": "3.9.20", "3.13": "3.13.1", "3.10": "3.10.4"})
        self.assertEqual(record.active_slots(), ["3.9", "3.10", "3.13"])

    def test_rejects_default_that_disagrees_with_its_line(self):
        with self.assertRaises(mp.ManagerError):
            mp.PointerRecord(default="3.12.13", lines={"3.12": "3.12.14"}).validate()
        with self.assertRaises(mp.ManagerError):
            mp.PointerRecord(default="3.12.13").validate()

    def test_rejects_version_on_wrong_line(self):
        with self.assertRaises(mp.ManagerError):
            mp.PointerRecord(lines={"3.12": "3.13.1"}).validate()

    def test_rejects_non_versions(self):
        with self.assertRaises(mp.ManagerError):
            mp.PointerRecord(lines={"3.12": "latest"}).validate()

    def test_rejects_duplicate_alias_names_case_insensitively(self):
        record = mp.PointerRecord(default="3.12.14",
                                  lines={"3.12": "3.12.14", "3.13": "3.13.1"},
                                  aliases={"3.12": "py", "3.13": "PY"})
        with self.assertRaises(mp.ManagerError):
            record.validate()

    def test_rejects_rename_onto_another_default_name(self):
        record = mp.PointerRecord(default="3.12.14",
                                  lines={"3.12": "3.12.14", "3.13": "3.13.1"},
                                  aliases={"3.12": "python3.13"})
        with self.assertRaises(mp.ManagerError):
            record.validate()

    def test_manage_python_is_reserved_for_the_manager(self):
        mp.check_alias_name("manage-python", mp.SELF)
        for slot in (mp.DEFAULT, "3.12", None):
            with self.subTest(slot=slot), self.assertRaises(mp.ManagerError):
                mp.check_alias_name("Manage-Python", slot)

    def test_alias_name_rules(self):
        for good in ("python", "py312", "python3.12", "py-3.12", "py_312", "cpython+"):
            mp.check_alias_name(good)
        for bad in ("", "-py", ".py", "py/312", "py\\312", "py 312", 'py"', "py$x",
                    "py;rm", "manage-python", "NUL", "con.txt", "python.cmd",
                    "python.PS1", "p" * 65):
            with self.subTest(name=bad), self.assertRaises(mp.ManagerError):
                mp.check_alias_name(bad)


class TestPointerFormats(Scratch):

    def record(self):
        return mp.PointerRecord(default="3.12.14",
                                lines={"3.12": "3.12.14", "3.13": "3.13.15"},
                                aliases={"3.12": "py312"})

    def test_proposal_example_parses(self):
        record = mp.parse_pointer(PROPOSAL_POINTER, "posix")
        self.assertEqual(record, self.record())

    def test_posix_render_matches_proposal_body(self):
        text = mp.render_pointer(self.record(), "posix", self.posix_paths())
        body = "".join(l + "\n" for l in text.splitlines() if not l.startswith("#"))
        self.assertEqual(body, PROPOSAL_POINTER)
        self.assertIn("# ~/.config/python-manager/python-manager.env\n", text)
        self.assertIn("never touches", text)

    def test_cmd_and_ps1_syntax(self):
        paths = self.windows_paths()
        cmd = mp.render_pointer(self.record(), "cmd", paths)
        ps1 = mp.render_pointer(self.record(), "ps1", paths)
        self.assertIn('set "PYTHON_MANAGER_3_12=3.12.14"\n', cmd)
        self.assertIn('$env:PYTHON_MANAGER_3_12 = "3.12.14"\n', ps1)
        self.assertTrue(cmd.startswith("rem %LOCALAPPDATA%"))
        self.assertTrue(ps1.startswith("# %LOCALAPPDATA%"))

    def test_round_trip_every_format(self):
        paths = self.windows_paths()
        for fmt in ("posix", "cmd", "ps1"):
            with self.subTest(fmt=fmt):
                text = mp.render_pointer(self.record(), fmt, paths)
                self.assertEqual(mp.parse_pointer(text, fmt), self.record())
                crlf = text.replace("\n", "\r\n")
                self.assertEqual(mp.parse_pointer(crlf, fmt), self.record())

    def test_three_formats_carry_same_keys_and_values(self):
        paths = self.windows_paths()
        parsed = [mp.parse_pointer(mp.render_pointer(self.record(), f, paths), f).to_items()
                  for f in ("posix", "cmd", "ps1")]
        self.assertEqual(parsed[0], parsed[1])
        self.assertEqual(parsed[1], parsed[2])

    def test_parse_tolerates_comments_bom_and_case(self):
        text = '﻿@echo off\nrem hello\n:: note\nREM\nSET "python_manager_3_12=3.12.1"\n'
        record = mp.parse_pointer(text, "cmd")
        self.assertEqual(record.lines, {"3.12": "3.12.1"})

    def test_parse_refuses_foreign_lines(self):
        for text in ('export PATH="/tmp"\n', 'PYTHON_MANAGER_3_12=3.12.1\n',
                     'PYTHON_MANAGER_3_12="$(touch /tmp/x)"\n'):
            with self.subTest(text=text), self.assertRaises(mp.ManagerError):
                mp.parse_pointer(text, "posix")

    def test_parse_refuses_unsafe_values(self):
        for value in ("3.12.1; rm -rf ~", "`id`", "a b", "%PATH%"):
            with self.subTest(value=value), self.assertRaises(mp.ManagerError):
                mp.parse_pointer(f'PYTHON_MANAGER_ALIAS_DEFAULT="{value}"\n', "posix")

    def test_unknown_keys_survive_a_rewrite(self):
        text = PROPOSAL_POINTER + 'PYTHON_MANAGER_FUTURE="yes"\n'
        record = mp.parse_pointer(text, "posix")
        self.assertEqual(record.extra, {"PYTHON_MANAGER_FUTURE": "yes"})
        again = mp.render_pointer(record, "posix", self.posix_paths())
        self.assertIn('PYTHON_MANAGER_FUTURE="yes"', again)

    def test_unknown_alias_slot_refused(self):
        with self.assertRaises(mp.ManagerError):
            mp.parse_pointer('PYTHON_MANAGER_ALIAS_PIP="pip"\n', "posix")

    def test_read_missing_pointer_is_empty(self):
        record = mp.read_pointer(self.posix_paths())
        self.assertEqual(record.to_items(), [])

    def test_read_names_the_file_on_error(self):
        paths = self.posix_paths()
        paths.pointer_dir.mkdir(parents=True)
        paths.pointer_file.write_text("garbage\n")
        with self.assertRaisesRegex(mp.ManagerError, "python-manager.env"):
            mp.read_pointer(paths)

    @POSIX_ONLY
    def test_posix_write_is_owner_only_and_leaves_no_temp_files(self):
        paths = self.posix_paths()
        mp.write_pointer(self.record(), paths)
        self.assertEqual(stat.S_IMODE(paths.pointer_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(paths.pointer_dir.stat().st_mode), 0o700)
        self.assertEqual(os.listdir(paths.pointer_dir), ["python-manager.env"])
        self.assertEqual(mp.read_pointer(paths), self.record())

    def test_windows_write_produces_both_files_with_crlf(self):
        paths = self.windows_paths()
        mp.write_pointer(self.record(), paths)
        for path in paths.pointer_files.values():
            raw = path.read_bytes()
            self.assertIn(b"\r\n", raw)
            self.assertNotIn(b"\r\r\n", raw)
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertEqual(mp.read_pointer(paths), self.record())

    def test_write_failure_keeps_old_pointer_and_cleans_up(self):
        paths = self.posix_paths()
        mp.write_pointer(self.record(), paths)
        before = paths.pointer_file.read_bytes()
        changed = self.record()
        changed.switch("3.12.13")
        with mock.patch.object(mp.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                mp.write_pointer(changed, paths)
        self.assertEqual(paths.pointer_file.read_bytes(), before)
        self.assertEqual(os.listdir(paths.pointer_dir), ["python-manager.env"])

    def test_write_refuses_invalid_record_before_touching_disk(self):
        paths = self.posix_paths()
        mp.write_pointer(self.record(), paths)
        before = paths.pointer_file.read_bytes()
        bad = self.record()
        bad.aliases["3.13"] = "py312"
        with self.assertRaises(mp.ManagerError):
            mp.write_pointer(bad, paths)
        self.assertEqual(paths.pointer_file.read_bytes(), before)

    @POSIX_ONLY
    def test_refuses_pointer_dir_broader_than_owner_only(self):
        paths = self.posix_paths()
        paths.pointer_dir.mkdir(parents=True)
        paths.pointer_dir.chmod(0o755)
        with self.assertRaisesRegex(mp.ManagerError, "permissions"):
            mp.write_pointer(self.record(), paths)

    @POSIX_ONLY
    def test_posix_pointer_is_sourceable_by_sh(self):
        paths = self.posix_paths()
        mp.write_pointer(self.record(), paths)
        out = subprocess.run(
            ["/bin/sh", "-c", '. "$1"; echo "$PYTHON_MANAGER_DEFAULT $PYTHON_MANAGER_ALIAS_3_12"',
             "sh", str(paths.pointer_file)],
            capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip(), "3.12.14 py312")


# ── PROVENANCE ────────────────────────────────────────────────────────────────

class TestProvenance(Scratch):

    NOW = datetime(2026, 9, 29, 14, 2, 11, tzinfo=timezone.utc)
    ASSET = "cpython-3.12.14+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
    SOURCE = ("https://github.com/astral-sh/python-build-standalone/releases/download/"
              "20260924/" + ASSET)

    def write_runtime(self, **overrides):
        args = dict(asset=self.ASSET, sha256="0f" * 32, source=self.SOURCE,
                    version="3.12.14", build="20260924",
                    triple="x86_64-unknown-linux-gnu", now=self.NOW)
        args.update(overrides)
        return mp.write_provenance(self.tmp, **args)

    def test_runtime_provenance_matches_proposal(self):
        with mock.patch.object(mp, "manager_version", return_value="0.3.0"):
            path = self.write_runtime()
        self.assertEqual(path.read_text(encoding="utf-8"),
                         "manager: manage-python 0.3.0\n"
                         f"asset: {self.ASSET}\n"
                         f"sha256: {'0f' * 32}\n"
                         f"source: {self.SOURCE}\n"
                         "installed: 2026-09-29T14:02:11Z\n"
                         "version: 3.12.14\n"
                         "build: 20260924\n"
                         "triple: x86_64-unknown-linux-gnu\n")

    def test_manager_provenance_has_first_five_keys_only(self):
        path = mp.write_provenance(self.tmp, asset="osat-manager-python-0.3.0.tar.gz",
                                   sha256="ab" * 32, source="local archive (/x)", now=self.NOW)
        keys = [line.split(":", 1)[0] for line in path.read_text().splitlines()]
        self.assertEqual(tuple(keys), mp.PROVENANCE_KEYS)

    def test_first_five_keys_match_restic_order(self):
        restic_keys = tuple(l.split(":", 1)[0] for l in RESTIC_PROVENANCE.splitlines())
        self.assertEqual(mp.PROVENANCE_KEYS, restic_keys)
        self.assertEqual(mp.RUNTIME_PROVENANCE_KEYS[:5], restic_keys)

    def test_reads_restic_provenance(self):
        fields = mp.parse_provenance(RESTIC_PROVENANCE)
        self.assertEqual(fields["manager"], "osat-fluent-restic-tool 0.4.4")
        self.assertEqual(fields["source"],
                         "https://github.com/restic/restic/releases/download/v0.19.1/"
                         "restic_0.19.1_linux_amd64.bz2")
        self.assertEqual(fields["installed"], "2026-08-11T09:15:02Z")
        self.assertNotIn("version", fields)

    def test_round_trip(self):
        self.write_runtime()
        fields = mp.read_provenance(self.tmp)
        self.assertEqual(fields["triple"], "x86_64-unknown-linux-gnu")
        self.assertEqual(fields["build"], "20260924")
        self.assertEqual(fields["source"], self.SOURCE)

    def test_reader_is_lenient(self):
        text = "﻿manager: x 1\r\nfuture_key: later\r\nnot a pair\r\n\r\nmanager: second\r\n"
        fields = mp.parse_provenance(text)
        self.assertEqual(fields, {"manager": "x 1", "future_key": "later"})

    def test_missing_provenance_is_empty(self):
        self.assertEqual(mp.read_provenance(self.tmp / "nowhere"), {})

    def test_timestamp_is_utc(self):
        from datetime import timedelta
        local = datetime(2026, 9, 29, 10, 2, 11, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(mp.utc_timestamp(local), "2026-09-29T14:02:11Z")

    @POSIX_ONLY
    def test_owner_only(self):
        path = self.write_runtime()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_refuses_bad_values(self):
        for overrides in ({"sha256": "abc"}, {"sha256": "zz" * 32},
                          {"source": "https://x\nmanager: forged"},
                          {"asset": ""}, {"version": "3.12"}):
            with self.subTest(overrides=overrides), self.assertRaises(mp.ManagerError):
                self.write_runtime(**overrides)
        self.assertFalse((self.tmp / "PROVENANCE").exists())

    def test_runtime_fields_come_together(self):
        with self.assertRaises(mp.ManagerError):
            self.write_runtime(build=None)

    def test_uppercase_sha_is_normalised(self):
        self.write_runtime(sha256="AB" * 32)
        self.assertEqual(mp.read_provenance(self.tmp)["sha256"], "ab" * 32)


# ── Platform triple ───────────────────────────────────────────────────────────

def elf_bytes(interp=None, is_64=True, little=True):
    """A minimal ELF image: header, one or two program headers, interpreter."""
    order = "<" if little else ">"
    ehsize, phentsize = (64, 56) if is_64 else (52, 32)
    headers = [(1, 0, 0)]                                   # a PT_LOAD to skip
    data_off = ehsize + phentsize * 2
    if interp is not None:
        payload = interp.encode() + b"\0"
        headers.append((mp.PT_INTERP, data_off, len(payload)))
    else:
        payload = b""
        headers.append((1, 0, 0))
    ident = b"\x7fELF" + bytes([2 if is_64 else 1, 1 if little else 2, 1]) + b"\0" * 9
    if is_64:
        header = ident + struct.pack(order + "HHIQQQIHHHHHH", 2, 62, 1, 0, ehsize, 0, 0,
                                     ehsize, phentsize, len(headers), 0, 0, 0)
        phdrs = b"".join(struct.pack(order + "IIQQQQQQ", t, 0, off, 0, 0, size, size, 0)
                         for t, off, size in headers)
    else:
        header = ident + struct.pack(order + "HHIIIIIHHHHHH", 2, 40, 1, 0, ehsize, 0, 0,
                                     ehsize, phentsize, len(headers), 0, 0, 0)
        phdrs = b"".join(struct.pack(order + "IIIIIIII", t, off, 0, 0, size, size, 0, 0)
                         for t, off, size in headers)
    return header + phdrs + payload


class TestTriple(Scratch):

    def test_common_cases_from_proposal(self):
        cases = [
            (("Linux", "x86_64", "gnu"), "x86_64-unknown-linux-gnu"),
            (("Linux", "aarch64", "gnu"), "aarch64-unknown-linux-gnu"),
            (("Linux", "x86_64", "musl"), "x86_64-unknown-linux-musl"),
            (("Linux", "aarch64", "musl"), "aarch64-unknown-linux-musl"),
            (("Darwin", "arm64", None), "aarch64-apple-darwin"),
            (("Darwin", "x86_64", None), "x86_64-apple-darwin"),
            (("Windows", "AMD64", None), "x86_64-pc-windows-msvc"),
            (("Windows", "ARM64", None), "aarch64-pc-windows-msvc"),
        ]
        for args, triple in cases:
            with self.subTest(args=args):
                self.assertEqual(mp.select_triple(*args), triple)

    def test_other_published_linux_and_windows_builds(self):
        self.assertEqual(mp.select_triple("Linux", "armv7l", "gnu"), "armv7-unknown-linux-gnueabihf")
        self.assertEqual(mp.select_triple("Linux", "ppc64le", "gnu"), "ppc64le-unknown-linux-gnu")
        self.assertEqual(mp.select_triple("Linux", "riscv64", "gnu"), "riscv64-unknown-linux-gnu")
        self.assertEqual(mp.select_triple("Linux", "s390x", "gnu"), "s390x-unknown-linux-gnu")
        self.assertEqual(mp.select_triple("Windows", "x86", None), "i686-pc-windows-msvc")

    def test_rosetta_selects_apple_silicon(self):
        self.assertEqual(mp.select_triple("Darwin", "x86_64", translated=True),
                         "aarch64-apple-darwin")
        self.assertEqual(mp.select_triple("Darwin", "arm64", translated=True),
                         "aarch64-apple-darwin")

    def test_translated_flag_ignored_off_macos(self):
        self.assertEqual(mp.select_triple("Linux", "x86_64", "gnu", translated=True),
                         "x86_64-unknown-linux-gnu")

    def test_never_selects_x86_64_variants(self):
        self.assertFalse(any("_v" in t for t in mp.TRIPLES.values()))

    def test_unsupported_platforms_fail_clearly(self):
        for args in (("FreeBSD", "amd64", None), ("OpenBSD", "amd64", None),
                     ("Linux", "armv7l", "musl"), ("Linux", "mips", "gnu"),
                     ("Linux", "x86_64", None)):
            with self.subTest(args=args):
                with self.assertRaisesRegex(mp.ManagerError, "Supported:"):
                    mp.select_triple(*args)

    def test_rosetta_probe(self):
        def fake(out, code=0):
            return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=out, stderr="")
        self.assertTrue(mp.rosetta_translated(fake("1\n")))
        self.assertFalse(mp.rosetta_translated(fake("0\n")))
        self.assertFalse(mp.rosetta_translated(fake("")))          # Intel Mac
        self.assertFalse(mp.rosetta_translated(fake("1\n", 1)))

        def missing(*a, **k):
            raise FileNotFoundError("/usr/sbin/sysctl")
        self.assertFalse(mp.rosetta_translated(missing))

    def test_elf_interpreter_64_and_32_bit(self):
        cases = [
            (elf_bytes("/lib/ld-musl-x86_64.so.1"), "/lib/ld-musl-x86_64.so.1"),
            (elf_bytes("/lib/ld-linux-armhf.so.3", is_64=False), "/lib/ld-linux-armhf.so.3"),
            (elf_bytes("/lib/ld64.so.1", little=False), "/lib/ld64.so.1"),
            (elf_bytes(None), None),                               # static binary
            (b"#!/bin/sh\necho hi\n", None),
            (b"\x7fELF\x02", None),                                # truncated
        ]
        for index, (data, expected) in enumerate(cases):
            path = self.tmp / f"bin{index}"
            path.write_bytes(data)
            with self.subTest(expected=expected, index=index):
                self.assertEqual(mp.elf_interpreter(str(path)), expected)
        self.assertIsNone(mp.elf_interpreter(str(self.tmp / "missing")))

    @unittest.skipUnless(sys.platform.startswith("linux"), "reads this host's /bin/sh")
    def test_elf_interpreter_on_this_host(self):
        interp = mp.elf_interpreter("/bin/sh")
        if interp is not None:
            self.assertIn("ld-", os.path.basename(interp))

    def test_detect_libc(self):
        def interp(value):
            return lambda path: value
        no_alpine = lambda path: False

        # glibc in the running interpreter settles it, even with musl installed.
        self.assertEqual(mp.detect_libc(lambda: ("glibc", "2.39"),
                                        interp("/lib/ld-musl-x86_64.so.1"), no_alpine), "gnu")
        # Alpine: a musl Python and a musl /bin/sh.
        self.assertEqual(mp.detect_libc(lambda: ("", ""),
                                        interp("/lib/ld-musl-aarch64.so.1"), no_alpine), "musl")
        # A statically linked (musl) Python on a glibc host.
        self.assertEqual(mp.detect_libc(lambda: ("", ""),
                                        interp("/lib64/ld-linux-x86-64.so.2"), no_alpine), "gnu")
        # NixOS: the loader lives in the store.
        self.assertEqual(mp.detect_libc(
            lambda: ("", ""),
            interp("/nix/store/abc-glibc-2.39/lib/ld-linux-x86-64.so.2"), no_alpine), "gnu")
        # A static busybox /bin/sh: fall back to the Alpine marker.
        self.assertEqual(mp.detect_libc(lambda: ("", ""), interp(None),
                                        lambda path: path == "/etc/alpine-release"), "musl")
        self.assertEqual(mp.detect_libc(lambda: ("", ""), interp(None), no_alpine), "gnu")

    def test_detect_triple_wires_probes(self):
        with mock.patch.object(mp.platform, "system", return_value="Darwin"), \
             mock.patch.object(mp.platform, "machine", return_value="x86_64"), \
             mock.patch.object(mp, "rosetta_translated", return_value=True):
            self.assertEqual(mp.detect_triple(), "aarch64-apple-darwin")
        with mock.patch.object(mp.platform, "system", return_value="Linux"), \
             mock.patch.object(mp.platform, "machine", return_value="aarch64"), \
             mock.patch.object(mp, "detect_libc", return_value="musl"):
            self.assertEqual(mp.detect_triple(), "aarch64-unknown-linux-musl")


# ── Status ────────────────────────────────────────────────────────────────────

PROPOSAL_STATUS = """3.12
  aliases     python3.12  python
    default     3.12.14
    installed   3.12.13
    archived    3.12.12+20260715

3.13
  aliases     python3.13
    default     3.13.15
"""


class TestStatus(Scratch):

    def proposal_tree(self, aliases=None):
        paths = self.posix_paths()
        for version in ("3.12.14", "3.12.13", "3.13.15"):
            self.make_runtime(paths, version)
        for build in ("3.12.14+20260924", "3.12.13+20260801", "3.12.12+20260715",
                      "3.13.15+20260924"):
            self.make_archive(paths, build)
        (paths.manager_dir / "0.3.0").mkdir(parents=True)
        record = mp.PointerRecord(default="3.12.14",
                                  lines={"3.12": "3.12.14", "3.13": "3.13.15"},
                                  aliases=aliases or {})
        return paths, record

    def status(self, paths, record):
        lines, warnings = mp.collect_status(paths, record)
        return mp.format_status(lines), warnings

    def test_matches_proposal_example(self):
        paths, record = self.proposal_tree()
        text, _ = self.status(paths, record)
        self.assertEqual(text, PROPOSAL_STATUS)

    def test_python_moves_with_a_switch_across_lines(self):
        paths, record = self.proposal_tree()
        record.switch("3.13.15")
        text, _ = self.status(paths, record)
        self.assertIn("3.12\n  aliases     python3.12\n", text)
        self.assertIn("3.13\n  aliases     python3.13  python\n", text)

    def test_renamed_alias_appears_under_new_name(self):
        paths, record = self.proposal_tree(aliases={"3.12": "py312", mp.DEFAULT: "py"})
        text, _ = self.status(paths, record)
        self.assertIn("  aliases     py312  py\n", text)

    def test_several_installed_versions_newest_first(self):
        paths, record = self.proposal_tree()
        self.make_runtime(paths, "3.12.9")
        self.make_runtime(paths, "3.12.10")
        text, _ = self.status(paths, record)
        self.assertIn("    installed   3.12.13  3.12.10  3.12.9\n", text)

    def test_ignores_non_version_entries(self):
        paths, record = self.proposal_tree()
        (paths.share_dir / "3.12").mkdir()
        (paths.share_dir / "notes.txt").write_text("x")
        (paths.archive_dir / "junk").mkdir()
        text, _ = self.status(paths, record)
        self.assertEqual(text, PROPOSAL_STATUS)

    def test_archived_only_line_is_shown_without_aliases(self):
        paths = self.posix_paths()
        self.make_archive(paths, "3.11.9+20240814")
        text, warnings = self.status(paths, mp.PointerRecord())
        self.assertEqual(text, "3.11\n    archived    3.11.9+20240814\n")
        self.assertEqual(warnings, [])

    def test_installed_but_no_pointer(self):
        paths = self.posix_paths()
        self.make_runtime(paths, "3.12.14")
        text, _ = self.status(paths, mp.PointerRecord())
        self.assertEqual(text, "3.12\n    installed   3.12.14\n")

    def test_empty(self):
        text, warnings = self.status(self.posix_paths(), mp.PointerRecord())
        self.assertEqual(text, "No Python versions installed.\n")
        self.assertEqual(warnings, [])

    def test_warns_when_pointer_names_missing_runtime(self):
        paths, record = self.proposal_tree()
        shutil.rmtree(paths.runtime_dir("3.13.15"))
        _, warnings = self.status(paths, record)
        self.assertTrue(any("3.13.15" in w and "not installed" in w for w in warnings))

    def test_warns_about_missing_alias_files(self):
        paths, record = self.proposal_tree()
        _, warnings = self.status(paths, record)
        self.assertEqual(len([w for w in warnings if "does not exist" in w]), 3)
        paths.bin_dir.mkdir(parents=True)
        for name in ("python", "python3.12", "python3.13"):
            (paths.bin_dir / name).write_text("#")
        _, warnings = self.status(paths, record)
        self.assertEqual(warnings, [])

    def test_cli_status_reads_the_filesystem(self):
        paths, record = self.proposal_tree()
        mp.write_pointer(record, paths)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(mp, "Paths", return_value=paths), \
             redirect_stdout(out), redirect_stderr(err):
            code = mp.main(["--status"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), PROPOSAL_STATUS)
        self.assertIn("[manage-python] warning:", err.getvalue())

    def test_cli_status_reports_a_broken_pointer(self):
        paths = self.posix_paths()
        paths.pointer_dir.mkdir(parents=True)
        paths.pointer_file.write_text('PYTHON_MANAGER_3_12="3.13.1"\n')
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(mp, "Paths", return_value=paths), \
             redirect_stdout(out), redirect_stderr(err):
            code = mp.main(["--status"])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("[manage-python] ERROR:", err.getvalue())


class TestCli(unittest.TestCase):

    def test_version_comes_from_the_version_file(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(mp.main(["--version"]), 0)
        expected = (_SCRIPT.parent / "VERSION").read_text().strip()
        self.assertEqual(out.getvalue(), f"manage-python {expected}\n")

    def test_no_version_constant(self):
        self.assertFalse(hasattr(mp, "MANAGER_VERSION"))

    def test_manager_version_reads_its_own_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(mp.manager_version(Path(tmp)), "unknown")
            (Path(tmp) / "VERSION").write_text("0.3.0\n")
            self.assertEqual(mp.manager_version(Path(tmp)), "0.3.0")

    def test_actions_are_mutually_exclusive(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            mp.main(["--status", "--version"])
        self.assertEqual(caught.exception.code, 2)

    def test_no_action_is_usage_error(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(mp.main([]), 2)
        self.assertIn("usage: manage-python", err.getvalue())

    def test_unknown_option_is_usage_error(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            mp.main(["--bogus"])
        self.assertEqual(caught.exception.code, 2)


# ── Aliases ───────────────────────────────────────────────────────────────────

class TestAliasRendering(Scratch):

    def test_nix_alias_matches_proposal_header(self):
        paths = self.posix_paths()
        text = mp.render_alias(mp.read_template("posix"), "#",
                               paths.display(paths.bin_dir / "python3.12"),
                               "PYTHON_MANAGER_3_12")
        self.assertTrue(text.startswith(
            "#!/bin/sh\n"
            "#\n"
            "# source\n"
            "#   project: osat-manager-python\n"
            "#   path: scripts/nix/alias.template\n"
            "# generated\n"
            "#   path: ~/.local/bin/python3.12\n"
            "#   by: manage-python.py\n"
            "#\n"
            "# Do not edit generated aliases; regenerated on --install, --switch and --alias.\n"))
        self.assertIn('. "$_cfg/python-manager.env"\n[ -f "$_cfg/env" ] && . "$_cfg/env"\n', text)
        self.assertIn("/python-manager/${PYTHON_MANAGER_3_12:?", text)
        self.assertTrue(text.rstrip().endswith('/python/bin/python3" "$@"'))
        self.assertNotIn("@", text.replace('"$@"', ""))

    def test_windows_aliases(self):
        cmd = mp.render_alias(mp.read_template("cmd"), "rem",
                              r"%LOCALAPPDATA%\Programs\python3.12.cmd", "PYTHON_MANAGER_3_12")
        self.assertIn("rem generated\nrem   path: %LOCALAPPDATA%\\Programs\\python3.12.cmd\n"
                      "rem   by: manage-python.py\n", cmd)
        self.assertIn("setlocal\n", cmd)
        self.assertIn(r'"%LOCALAPPDATA%\python-manager\%PYTHON_MANAGER_3_12%\python\python.exe" %*'
                      "\nexit /b %ERRORLEVEL%\n", cmd)
        self.assertIn("if not defined PYTHON_MANAGER_3_12 goto :unset\n", cmd)
        self.assertLess(cmd.index("python-manager.env.cmd"), cmd.index("env.cmd\" call"))

        ps1 = mp.render_alias(mp.read_template("ps1"), "#",
                              r"%LOCALAPPDATA%\Programs\python3.12.ps1", "PYTHON_MANAGER_3_12")
        self.assertIn("#   by: manage-python.py\n", ps1)
        self.assertIn(r"\$env:PYTHON_MANAGER_3_12\python\python.exe" + '" @args', ps1)
        self.assertIn("$osatExit = $LASTEXITCODE", ps1)
        self.assertTrue(ps1.endswith("}\nexit $osatExit\n"))
        self.assertLess(ps1.index("$osatSnapshot = @{}"), ps1.index("python-manager.env.ps1"))
        self.assertLess(ps1.index("python-manager.env.ps1"), ps1.index('env.ps1") {'))
        self.assertLess(ps1.index("finally {"), ps1.index("exit $osatExit"))

    def test_generic_alias_reads_default_key(self):
        text = mp.render_alias(mp.read_template("posix"), "#", "~/.local/bin/python",
                               "PYTHON_MANAGER_DEFAULT")
        self.assertIn("${PYTHON_MANAGER_DEFAULT:?", text)

    def test_template_errors(self):
        with self.assertRaisesRegex(mp.ManagerError, "unknown token"):
            mp.render_alias("# generates\n#   path: @ALIAS_PATH@\n@OOPS@\n", "#", "p", "K")
        with self.assertRaisesRegex(mp.ManagerError, "generates"):
            mp.render_alias("#!/bin/sh\nexec x\n", "#", "p", "K")
        with self.assertRaisesRegex(mp.ManagerError, "template not found"):
            mp.read_template("posix", self.tmp)


class TestAliasOwnership(Scratch):

    def write(self, name, data):
        path = self.tmp / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return path

    def test_absent(self):
        self.assertEqual(mp.alias_owner(self.tmp / "python"), "absent")

    def test_ours_every_format(self):
        paths = self.windows_paths()
        for fmt, comment in (("posix", "#"), ("cmd", "rem"), ("ps1", "#")):
            text = mp.render_alias(mp.read_template(fmt), comment, "p", "PYTHON_MANAGER_3_12")
            with self.subTest(fmt=fmt):
                self.assertEqual(mp.alias_owner(self.write(fmt, text)), "ours")
                crlf = self.write(fmt + "-crlf", text.replace("\n", "\r\n"))
                self.assertEqual(mp.alias_owner(crlf), "ours")

    def test_foreign_files(self):
        cases = {
            "old-installer": '#!/bin/sh\n# Rendered by install-python.py. Do not edit.\nexec "x" "$@"\n',
            "restic": "#!/bin/sh\n#\n# source\n# generated\n#   path: x\n#   by: install-restic.py\n",
            "template": mp.read_template("posix"),
            "by-in-source-block": "#!/bin/sh\n# source\n#   by: manage-python.py\n",
            "by-after-command": '#!/bin/sh\necho hi\n# generated\n#   by: manage-python.py\n',
            "by-prefixed": "#!/bin/sh\n# generated\n#   by: manage-python.py.bak\n",
            "binary": b"\x7fELF\x02\x01\x01\x00\xff\xfe",
            "empty": "",
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertEqual(mp.alias_owner(self.write(name, data)), "foreign")

    @POSIX_ONLY
    def test_symlink_is_foreign_even_to_our_own_alias(self):
        ours = self.write("ours", mp.render_alias(mp.read_template("posix"), "#", "p", "K"))
        link = self.tmp / "python3.12"
        link.symlink_to(ours)
        self.assertEqual(mp.alias_owner(link), "foreign")
        dangling = self.tmp / "dangling"
        dangling.symlink_to(self.tmp / "nowhere")
        self.assertEqual(mp.alias_owner(dangling), "foreign")


class TestWriteAlias(Scratch):

    @POSIX_ONLY
    def test_writes_executable_alias(self):
        paths = self.posix_paths()
        [path] = mp.write_alias(paths, "3.12", "python3.12")
        self.assertEqual(path, paths.bin_dir / "python3.12")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        self.assertEqual(mp.alias_owner(path), "ours")
        self.assertEqual(os.listdir(paths.bin_dir), ["python3.12"])

    def test_overwrites_its_own_alias(self):
        paths = self.posix_paths()
        mp.write_alias(paths, "3.12", "python3.12")
        mp.write_alias(paths, "3.12", "python3.12")
        self.assertEqual(mp.alias_owner(paths.bin_dir / "python3.12"), "ours")

    def test_refuses_foreign_file_and_suggests_alias(self):
        paths = self.posix_paths()
        paths.bin_dir.mkdir(parents=True)
        uv = paths.bin_dir / "python3.12"
        uv.write_text("#!/bin/sh\nexec uv-python \"$@\"\n")
        with self.assertRaisesRegex(mp.ManagerError, r"--alias python3\.12=<new-name>"):
            mp.write_alias(paths, "3.12", "python3.12")
        self.assertEqual(uv.read_text(), "#!/bin/sh\nexec uv-python \"$@\"\n")

    def test_generic_alias_refusal_names_python(self):
        paths = self.posix_paths()
        paths.bin_dir.mkdir(parents=True)
        (paths.bin_dir / "python").write_bytes(b"\x7fELF")
        with self.assertRaisesRegex(mp.ManagerError, "--alias python=<new-name>"):
            mp.write_alias(paths, mp.DEFAULT, "python")

    def test_windows_pair_written_with_crlf(self):
        paths = self.windows_paths()
        written = mp.write_alias(paths, mp.DEFAULT, "python")
        self.assertEqual([p.name for p in written], ["python.cmd", "python.ps1"])
        for path in written:
            raw = path.read_bytes()
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
            self.assertEqual(mp.alias_owner(path), "ours")
        self.assertIn(b"%PYTHON_MANAGER_DEFAULT%", written[0].read_bytes())

    def test_windows_foreign_ps1_blocks_both_files(self):
        paths = self.windows_paths()
        paths.bin_dir.mkdir(parents=True)
        (paths.bin_dir / "python.ps1").write_text("& py.exe @args\n")
        with self.assertRaises(mp.ManagerError):
            mp.write_alias(paths, mp.DEFAULT, "python")
        self.assertFalse((paths.bin_dir / "python.cmd").exists())

    def test_refuses_bad_names(self):
        with self.assertRaises(mp.ManagerError):
            mp.write_alias(self.posix_paths(), "3.12", "../python3.12")


@POSIX_ONLY
class TestPosixAliasEndToEnd(Scratch):
    """Run a rendered alias against a fake runtime: no download, real /bin/sh."""

    def setUp(self):
        super().setUp()
        self.env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin",
                    "XDG_DATA_HOME": str(self.tmp / "data"),
                    "XDG_CONFIG_HOME": str(self.tmp / "config")}
        self.paths = mp.Paths(windows=False, environ=self.env, home=self.home)
        for version, code in (("3.12.14", 7), ("3.12.13", 3)):
            runtime = self.paths.runtime_dir(version) / "python" / "bin"
            runtime.mkdir(parents=True)
            fake = runtime / "python3"
            fake.write_text('#!/bin/sh\nprintf "%s|" "{}" "$@"\necho "$OPERATOR"\n'
                            'exit {}\n'.format(version, code))
            fake.chmod(0o700)
        self.record = mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"})
        mp.write_pointer(self.record, self.paths)
        mp.write_alias(self.paths, "3.12", "python3.12")

    def run_alias(self):
        return subprocess.run([str(self.paths.bin_dir / "python3.12"), "-c", "a b", ""],
                              env=self.env, capture_output=True, text=True)

    def test_passes_arguments_and_exit_status_through(self):
        result = self.run_alias()
        self.assertEqual(result.stdout, "3.12.14|-c|a b||\n")
        self.assertEqual(result.returncode, 7)

    def test_switch_takes_effect_without_rewriting_alias(self):
        before = (self.paths.bin_dir / "python3.12").read_bytes()
        self.record.switch("3.12.13")
        mp.write_pointer(self.record, self.paths)
        result = self.run_alias()
        self.assertTrue(result.stdout.startswith("3.12.13|"))
        self.assertEqual(result.returncode, 3)
        self.assertEqual((self.paths.bin_dir / "python3.12").read_bytes(), before)

    def test_operator_env_is_read_after_the_pointer(self):
        self.paths.operator_env.write_text('OPERATOR=set-by-operator\nexport OPERATOR\n'
                                           'PYTHON_MANAGER_3_12="3.12.13"\n')
        result = self.run_alias()
        self.assertEqual(result.stdout, "3.12.13|-c|a b||set-by-operator\n")

    def test_missing_key_fails_with_a_message(self):
        mp.write_pointer(mp.PointerRecord(), self.paths)
        result = self.run_alias()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PYTHON_MANAGER_3_12", result.stderr)


# ── SELF: the manager's own alias ─────────────────────────────────────────────

class TestSelfPointer(Scratch):

    def record(self):
        return mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"},
                                self_version="0.3.0")

    def test_self_keys_round_trip_in_every_format(self):
        paths = self.windows_paths()
        for fmt in ("posix", "cmd", "ps1"):
            with self.subTest(fmt=fmt):
                text = mp.render_pointer(self.record(), fmt, paths)
                self.assertEqual(mp.parse_pointer(text, fmt), self.record())

    def test_key_order(self):
        self.assertEqual(self.record().to_items(), [
            ("PYTHON_MANAGER_DEFAULT", "3.12.14"), ("PYTHON_MANAGER_3_12", "3.12.14"),
            ("PYTHON_MANAGER_SELF", "0.3.0"),
            ("PYTHON_MANAGER_ALIAS_DEFAULT", "python"), ("PYTHON_MANAGER_ALIAS_3_12", "python3.12"),
            ("PYTHON_MANAGER_ALIAS_SELF", "manage-python")])

    def test_switch_never_changes_the_manager_version(self):
        record = self.record()
        record.switch("3.13.1")
        self.assertEqual(record.self_version, "0.3.0")

    def test_self_version_must_be_a_version(self):
        with self.assertRaises(mp.ManagerError):
            mp.parse_pointer('PYTHON_MANAGER_SELF="latest"\n', "posix")

    def test_manager_alias_can_be_renamed_but_not_taken(self):
        record = self.record()
        record.aliases[mp.SELF] = "mp"
        record.validate()
        record.aliases["3.12"] = "manage-python"
        with self.assertRaises(mp.ManagerError):
            record.validate()


class TestManagerAlias(Scratch):

    def test_posix_render(self):
        text = mp.render_alias(mp.read_template("posix", slot=mp.SELF), "#",
                               "~/.local/bin/manage-python", "PYTHON_MANAGER_SELF")
        self.assertIn("#   path: scripts/nix/manager-alias.template\n# generated\n"
                      "#   path: ~/.local/bin/manage-python\n#   by: manage-python.py\n", text)
        self.assertIn('_share="${XDG_DATA_HOME:-$HOME/.local/share}/python-manager"\n', text)
        self.assertIn('exec "$_share/${PYTHON_MANAGER_DEFAULT:?not set in $_cfg/python-manager.env}'
                      '/python/bin/python3" "$_share/manage-python/${PYTHON_MANAGER_SELF:?not set in '
                      '$_cfg/python-manager.env}/manage-python.py" "$@"\n', text)

    def test_windows_render(self):
        cmd = mp.render_alias(mp.read_template("cmd", slot=mp.SELF), "rem", "p", "PYTHON_MANAGER_SELF")
        self.assertIn(r'"%LOCALAPPDATA%\python-manager\%PYTHON_MANAGER_DEFAULT%\python\python.exe" '
                      r'"%LOCALAPPDATA%\python-manager\manage-python\%PYTHON_MANAGER_SELF%'
                      r'\manage-python.py" %*', cmd)
        self.assertIn("if not defined PYTHON_MANAGER_SELF goto :unset", cmd)
        ps1 = mp.render_alias(mp.read_template("ps1", slot=mp.SELF), "#", "p", "PYTHON_MANAGER_SELF")
        self.assertIn(r'\manage-python\$env:PYTHON_MANAGER_SELF\manage-python.py" @args', ps1)
        self.assertIn("finally {", ps1)
        self.assertTrue(ps1.endswith("exit $osatExit\n"))

    def test_write_alias_uses_manager_template(self):
        paths = self.posix_paths()
        [path] = mp.write_alias(paths, mp.SELF, "manage-python")
        self.assertIn("PYTHON_MANAGER_SELF", path.read_text())
        self.assertEqual(mp.alias_owner(path), "ours")

    @POSIX_ONLY
    def test_runs_the_named_manager_on_the_default_runtime(self):
        env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin",
               "XDG_DATA_HOME": str(self.tmp / "data"), "XDG_CONFIG_HOME": str(self.tmp / "config")}
        paths = mp.Paths(windows=False, environ=env, home=self.home)
        runtime = paths.interpreter(paths.runtime_dir("3.12.14"))
        runtime.parent.mkdir(parents=True)
        runtime.write_text('#!/bin/sh\nprintf "%s|" "3.12.14" "$@"\nexit 4\n')
        runtime.chmod(0o700)
        (paths.manager_dir / "0.3.0").mkdir(parents=True)
        mp.write_pointer(mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"},
                                          self_version="0.3.0"), paths)
        [alias] = mp.write_alias(paths, mp.SELF, "manage-python")
        result = subprocess.run([str(alias), "--status"], env=env, capture_output=True, text=True)
        script = paths.manager_dir / "0.3.0" / "manage-python.py"
        self.assertEqual(result.stdout, f"3.12.14|{script}|--status|")
        self.assertEqual(result.returncode, 4)

        mp.write_pointer(mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"}), paths)
        result = subprocess.run([str(alias)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PYTHON_MANAGER_SELF", result.stderr)


@unittest.skipUnless(shutil.which("pwsh"), "pwsh is not installed")
class TestPowerShellAliasRestoresEnvironment(Scratch):
    """The .ps1 alias must leave the calling session's environment as it was."""

    def test_session_environment_unchanged(self):
        paths = self.windows_paths()
        local = self.home / "AppData" / "Local"
        roaming = self.home / "AppData" / "Roaming"
        exe = paths.runtime_dir("3.12.14") / "python" / "python.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text('#!/bin/sh\necho "runtime $*"\nexit 7\n')
        exe.chmod(0o700)
        mp.write_pointer(mp.PointerRecord(default="3.12.14", lines={"3.12": "3.12.14"}), paths)
        paths.config_dir.mkdir(parents=True)
        (paths.config_dir / "env.ps1").write_text(
            '$env:OSAT_KEEP = "changed-by-operator"\n$env:OSAT_ADDED = "added-by-operator"\n')
        [_cmd, ps1] = mp.write_alias(paths, "3.12", "python3.12")
        session = f"""
$env:LOCALAPPDATA = '{local}'
$env:APPDATA = '{roaming}'
$env:OSAT_KEEP = 'before'
function Snap {{ (Get-ChildItem Env: | Sort-Object Name | ForEach-Object {{ "$($_.Name)=$($_.Value)" }}) -join "`n" }}
$before = Snap
& '{ps1}' first second
$code = $LASTEXITCODE
$after = Snap
if ($before -cne $after) {{ Write-Output "CHANGED"; exit 90 }}
exit $code
"""
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", session],
                                capture_output=True, text=True, timeout=120)
        self.assertNotIn("CHANGED", result.stdout, result.stderr)
        self.assertIn("runtime first second", result.stdout)
        self.assertEqual(result.returncode, 7, result.stderr)


# ── Lifecycle fixtures ────────────────────────────────────────────────────────

TRIPLE = "x86_64-unknown-linux-gnu"


def runtime_tarball(path, version, reports=None, windows=False, extra=None):
    """A stand-in for a python-build-standalone install_only tarball: an
    interpreter script that reports a version, and a standard library directory."""
    minor = ".".join(version.split(".")[:2])
    script = '#!/bin/sh\necho "{}"\n'.format(reports or version).encode()
    with tarfile.open(path, "w:gz") as tar:
        def add(name, data=b"", mode=0o644, kind=tarfile.REGTYPE, link=""):
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.size, info.linkname = kind, mode, len(data), link
            tar.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        add("python", kind=tarfile.DIRTYPE, mode=0o755)
        if windows:
            add("python/python.exe", script, 0o755)
            add("python/Lib", kind=tarfile.DIRTYPE, mode=0o755)
            add("python/Lib/os.py", b"# os\n")
        else:
            add("python/bin", kind=tarfile.DIRTYPE, mode=0o755)
            add(f"python/bin/python{minor}", script, 0o755)
            add("python/bin/python3", kind=tarfile.SYMTYPE, link=f"python{minor}")
            add(f"python/lib/python{minor}", kind=tarfile.DIRTYPE, mode=0o755)
            add(f"python/lib/python{minor}/os.py", b"# os\n")
        for name, data in (extra or {}).items():
            add(name, data)
    return path.read_bytes()


class FakeNetwork:
    """Serves releases, SHA256SUMS and tarballs from memory and records every URL."""

    def __init__(self):
        self.files = {}
        self.releases = {}          # build tag -> release dict
        self.calls = []
        self.offline = False

    def publish(self, build, data, sums=None):
        asset = build.asset
        self.files[build.url] = data
        digest = sums or hashlib.sha256(data).hexdigest()
        existing = self.files.get(build.sums_url, b"").decode()
        self.files[build.sums_url] = (existing + f"{digest}  {asset}\n").encode()
        release = self.releases.setdefault(build.build, {"tag_name": build.build, "assets": []})
        release["assets"].append({"name": asset})
        release["assets"].append({"name": asset.replace(build.triple, "x86_64_v3-unknown-linux-gnu")})

    def _call(self, url):
        self.calls.append(url)
        if self.offline:
            raise mp.ManagerError(f"network error for {url}: offline")

    def get_json(self, url):
        self._call(url)
        ordered = [self.releases[k] for k in sorted(self.releases, reverse=True)]
        if url.endswith("/releases/latest"):
            return ordered[0]
        page = int(url.rsplit("page=", 1)[1])
        return ordered[(page - 1) * 30:page * 30]

    def get_text(self, url):
        self._call(url)
        return self.files[url].decode()

    def download(self, url, destination):
        self._call(url)
        destination.write_bytes(self.files[url])

    def api_calls(self):
        return [c for c in self.calls if c.startswith("https://api.github.com/")]


class Lifecycle(Scratch):
    """A scratch home, a fake network and a manager release directory at 0.3.0."""

    NOW = datetime(2026, 9, 29, 14, 2, 11, tzinfo=timezone.utc)

    def setUp(self):
        super().setUp()
        bin_dir = str(self.tmp / "bin")
        self.env = {"HOME": str(self.home), "PATH": bin_dir + os.pathsep + "/usr/bin:/bin",
                    "XDG_DATA_HOME": str(self.tmp / "data"),
                    "XDG_CONFIG_HOME": str(self.tmp / "config"),
                    "XDG_STATE_HOME": str(self.tmp / "state"),
                    "XDG_BIN_HOME": bin_dir}
        self.paths = mp.Paths(windows=False, environ=self.env, home=self.home)
        self.net = FakeNetwork()
        self.source = self.tmp / "release"
        self.make_source("0.3.0")
        self.err = io.StringIO()
        patcher = redirect_stderr(self.err)
        patcher.__enter__()
        self.addCleanup(patcher.__exit__, None, None, None)

    def make_source(self, version):
        """A downloaded manager release: the script, VERSION and templates."""
        if self.source.exists():
            shutil.rmtree(self.source)
        (self.source / "scripts").mkdir(parents=True)
        shutil.copyfile(_SCRIPT, self.source / "manage-python.py")
        for sub in ("nix", "windows"):
            shutil.copytree(_SCRIPT.parent / "scripts" / sub, self.source / "scripts" / sub)
        (self.source / "VERSION").write_text(version + "\n")

    def publish(self, label, windows=False, reports=None, extra=None, triple=TRIPLE, sums=None):
        version, build = label.split("+")
        data = runtime_tarball(self.tmp / f"{label}.tar.gz", version,
                               reports=reports, windows=windows, extra=extra)
        self.net.publish(mp.Build(version, build, triple), data, sums=sums)
        return data

    def install(self, spec="", paths=None, triple=TRIPLE):
        return mp.cmd_install(spec, paths or self.paths, self.net, triple=triple,
                              source_dir=self.source, now=self.NOW)

    def pointer(self):
        return mp.read_pointer(self.paths)

    def status(self):
        lines, _warnings = mp.collect_status(self.paths, self.pointer())
        return mp.format_status(lines)

    def share_entries(self):
        return sorted(os.listdir(self.paths.share_dir))


# ── --install ─────────────────────────────────────────────────────────────────

class TestParseSpec(unittest.TestCase):

    def test_forms(self):
        self.assertEqual(mp.parse_spec(""), ("track", ""))
        self.assertEqual(mp.parse_spec("3.13"), ("minor", "3.13"))
        self.assertEqual(mp.parse_spec("3.12.14"), ("version", "3.12.14"))
        self.assertEqual(mp.parse_spec("3.12.14+20260924"), ("pinned", "3.12.14+20260924"))

    def test_rejects_everything_else(self):
        for spec in ("3", "latest", "3.12.14+", "v3.12.14", "3.14.0rc1", "3.12.14+abc", "../3.12"):
            with self.subTest(spec=spec), self.assertRaises(mp.UsageError):
                mp.parse_spec(spec)


class TestReleaseLookup(Lifecycle):

    def test_builds_in_release_ignores_variants_and_other_flavours(self):
        release = {"assets": [{"name": n} for n in (
            f"cpython-3.12.14+20260924-{TRIPLE}-install_only_stripped.tar.gz",
            f"cpython-3.12.13+20260924-{TRIPLE}-install_only_stripped.tar.gz",
            "cpython-3.12.14+20260924-x86_64_v3-unknown-linux-gnu-install_only_stripped.tar.gz",
            f"cpython-3.12.14+20260924-{TRIPLE}-install_only.tar.gz",
            f"cpython-3.13.1+20260924-{TRIPLE}-freethreaded-install_only_stripped.tar.gz",
            f"cpython-3.14.0rc1+20260924-{TRIPLE}-install_only_stripped.tar.gz",
            "SHA256SUMS")]}
        self.assertEqual([b.label for b in mp.builds_in_release(release, TRIPLE)],
                         ["3.12.14+20260924", "3.12.13+20260924"])

    def test_build_urls(self):
        build = mp.Build("3.12.14", "20260924", TRIPLE)
        self.assertEqual(build.url, "https://github.com/astral-sh/python-build-standalone/releases/"
                         "download/20260924/cpython-3.12.14+20260924-x86_64-unknown-linux-gnu-"
                         "install_only_stripped.tar.gz")
        self.assertTrue(build.sums_url.endswith("/download/20260924/SHA256SUMS"))

    def test_minor_line_takes_newest_patch_of_latest_release(self):
        self.publish("3.13.14+20260801")
        self.publish("3.13.15+20260924")
        self.publish("3.12.14+20260924")
        build = mp.resolve("minor", "3.13", TRIPLE, self.paths, self.net, "3.12")
        self.assertEqual(build.label, "3.13.15+20260924")
        self.assertEqual(self.net.api_calls(), [f"{mp.API_BASE}/releases/latest"])

    def test_track_uses_the_given_minor(self):
        self.publish("3.12.14+20260924")
        self.publish("3.13.15+20260924")
        self.assertEqual(mp.resolve("track", "", TRIPLE, self.paths, self.net, "3.12").version,
                         "3.12.14")

    def test_pinned_needs_no_network(self):
        build = mp.resolve("pinned", "3.12.14+20260924", TRIPLE, self.paths, self.net, "3.12")
        self.assertEqual(build.label, "3.12.14+20260924")
        self.assertEqual(self.net.calls, [])

    def test_version_searches_older_releases(self):
        self.publish("3.12.12+20260715")
        self.publish("3.12.14+20260924")
        build = mp.resolve("version", "3.12.12", TRIPLE, self.paths, self.net, "3.12")
        self.assertEqual(build.label, "3.12.12+20260715")

    def test_version_found_in_archive_needs_no_network(self):
        (self.paths.archive_dir / "3.12.12+20260601").mkdir(parents=True)
        (self.paths.archive_dir / "3.12.12+20260715").mkdir(parents=True)
        build = mp.resolve("version", "3.12.12", TRIPLE, self.paths, self.net, "3.12")
        self.assertEqual(build.label, "3.12.12+20260715")
        self.assertEqual(self.net.calls, [])

    def test_not_found(self):
        self.publish("3.12.14+20260924")
        with self.assertRaisesRegex(mp.ManagerError, "3.11.2"):
            mp.resolve("version", "3.11.2", TRIPLE, self.paths, self.net, "3.12")
        with self.assertRaisesRegex(mp.ManagerError, "no CPython 3.9"):
            mp.resolve("minor", "3.9", TRIPLE, self.paths, self.net, "3.12")

    def test_parse_sha256sums(self):
        sums = mp.parse_sha256sums("AB  file-a\n# comment\ncd *file-b\n\nbroken\n")
        self.assertEqual(sums, {"file-a": "ab", "file-b": "cd"})


class TestInstall(Lifecycle):

    def test_first_install(self):
        data = self.publish("3.12.14+20260924")
        self.assertEqual(self.install(), "3.12.14")
        build = mp.Build("3.12.14", "20260924", TRIPLE)
        digest = hashlib.sha256(data).hexdigest()

        runtime = self.paths.runtime_dir("3.12.14")
        self.assertTrue((runtime / "python" / "bin" / "python3").exists())
        self.assertEqual(mp.read_provenance(runtime), {
            "manager": "manage-python 0.3.0", "asset": build.asset, "sha256": digest,
            "source": build.url, "installed": "2026-09-29T14:02:11Z", "version": "3.12.14",
            "build": "20260924", "triple": TRIPLE})
        marker = runtime / "python" / "lib" / "python3.12" / "EXTERNALLY-MANAGED"
        self.assertIn("python3.12 -m venv .venv", marker.read_text())
        self.assertTrue(marker.read_text().startswith("[externally-managed]\nError="))

        entry = self.paths.archive_entry("3.12.14", "20260924")
        self.assertEqual(mp.sha256_of(entry / build.asset), digest)
        self.assertEqual(mp.read_provenance(entry)["sha256"], digest)

        self.assertEqual(self.pointer(), mp.PointerRecord(
            default="3.12.14", lines={"3.12": "3.12.14"}, self_version="0.3.0"))
        for name in ("python", "python3.12", "manage-python"):
            self.assertEqual(mp.alias_owner(self.paths.bin_dir / name), "ours", name)

        manager = self.paths.manager_dir / "0.3.0"
        self.assertEqual((manager / "VERSION").read_text(), "0.3.0\n")
        self.assertTrue((manager / "manage-python.py").is_file())
        self.assertTrue((manager / "scripts" / "nix" / "manager-alias.template").is_file())
        self.assertEqual(mp.manager_version(manager), "0.3.0")
        self.assertEqual(mp.read_provenance(manager)["sha256"],
                         mp.sha256_of(self.source / "manage-python.py"))

        self.assertEqual(self.share_entries(), ["3.12.14", "archive", "manage-python"])
        self.assertEqual(self.status(), "3.12\n  aliases     python3.12  python\n"
                                        "    default     3.12.14\n")

    @POSIX_ONLY
    def test_installed_tree_is_owner_only(self):
        self.publish("3.12.14+20260924")
        self.install()
        for root in (self.paths.runtime_dir("3.12.14"), self.paths.manager_dir / "0.3.0",
                     self.paths.archive_entry("3.12.14", "20260924")):
            for path in [root, *root.rglob("*")]:
                if not path.is_symlink():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0, path)

    def test_minor_line_install_moves_python_and_keeps_other_lines(self):
        self.publish("3.12.14+20260924")
        self.publish("3.13.15+20260924")
        self.install()
        self.assertEqual(self.install("3.13"), "3.13.15")
        record = self.pointer()
        self.assertEqual(record.default, "3.13.15")
        self.assertEqual(record.lines, {"3.12": "3.12.14", "3.13": "3.13.15"})
        self.assertTrue((self.paths.bin_dir / "python3.13").exists())

    def test_default_track_follows_the_current_default(self):
        self.publish("3.13.15+20260924")
        self.publish("3.12.14+20260924")
        self.install("3.13")
        self.assertEqual(self.install(), "3.13.15")

    def test_pinned_install_makes_no_api_call(self):
        self.publish("3.12.14+20260924")
        self.install("3.12.14+20260924")
        self.assertEqual(self.net.api_calls(), [])

    def test_already_installed_switches_without_downloading(self):
        self.publish("3.12.13+20260801")
        self.publish("3.12.14+20260924")
        self.install("3.12.13+20260801")
        self.install("3.12.14+20260924")
        calls = len(self.net.calls)
        self.install("3.12.13+20260801")
        self.assertEqual(len(self.net.calls), calls)
        self.assertEqual(self.pointer().default, "3.12.13")

    def test_offline_restore_from_archive(self):
        self.publish("3.12.13+20260801")
        self.publish("3.12.14+20260924")
        self.install("3.12.13+20260801")
        self.install("3.12.14+20260924")
        mp.cmd_remove("3.12.13", self.paths)
        self.net.offline = True
        self.install("3.12.13")
        provenance = mp.read_provenance(self.paths.runtime_dir("3.12.13"))
        self.assertTrue(provenance["source"].startswith("local archive ("))
        self.assertEqual(provenance["build"], "20260801")

    def test_tampered_archive_is_refused(self):
        self.publish("3.12.13+20260801")
        self.publish("3.12.14+20260924")
        self.install("3.12.13+20260801")
        self.install("3.12.14+20260924")
        mp.cmd_remove("3.12.13", self.paths)
        build = mp.Build("3.12.13", "20260801", TRIPLE)
        tarball = self.paths.archive_entry("3.12.13", "20260801") / build.asset
        tarball.write_bytes(tarball.read_bytes() + b"x")
        with self.assertRaisesRegex(mp.ManagerError, "recorded checksum"):
            self.install("3.12.13")
        self.assertFalse(self.paths.runtime_dir("3.12.13").exists())

    def assert_nothing_installed(self):
        self.assertFalse(self.paths.runtime_dir("3.12.14").exists())
        self.assertFalse(self.paths.archive_dir.exists())
        self.assertFalse(self.paths.pointer_file.exists())
        self.assertFalse(self.paths.bin_dir.exists())
        self.assertEqual([e for e in self.share_entries() if e.startswith(".")], [])

    def test_checksum_mismatch_installs_nothing(self):
        self.publish("3.12.14+20260924", sums="00" * 32)
        with self.assertRaisesRegex(mp.ManagerError, "checksum mismatch"):
            self.install()
        self.assert_nothing_installed()

    def test_asset_missing_from_sums_installs_nothing(self):
        self.publish("3.12.14+20260924")
        self.net.files[mp.Build("3.12.14", "20260924", TRIPLE).sums_url] = b"ab  other.tar.gz\n"
        with self.assertRaisesRegex(mp.ManagerError, "not listed in SHA256SUMS"):
            self.install()
        self.assert_nothing_installed()

    def test_failed_health_check_installs_nothing(self):
        self.publish("3.12.14+20260924", reports="3.11.0")
        with self.assertRaisesRegex(mp.ManagerError, "health check"):
            self.install()
        self.assert_nothing_installed()

    def test_unsafe_tarball_installs_nothing(self):
        self.publish("3.12.14+20260924", extra={"../escaped": b"x"})
        with self.assertRaisesRegex(mp.ManagerError, "unsafe|refusing"):
            self.install()
        self.assert_nothing_installed()
        self.assertFalse((self.paths.share_dir.parent / "escaped").exists())

    def test_legacy_member_checks(self):
        destination = self.tmp / "dest"
        destination.mkdir()
        for name, kind, link in (("/abs", tarfile.REGTYPE, ""), ("a/../../b", tarfile.REGTYPE, ""),
                                 ("dev", tarfile.CHRTYPE, ""), ("l", tarfile.SYMTYPE, "../../etc"),
                                 ("l2", tarfile.SYMTYPE, "/etc/passwd")):
            info = tarfile.TarInfo(name)
            info.type, info.linkname = kind, link
            with self.subTest(name=name), self.assertRaises(mp.ManagerError):
                mp._check_member(info, destination)
        ok = tarfile.TarInfo("python/bin/python3")
        ok.type, ok.linkname = tarfile.SYMTYPE, "python3.12"
        mp._check_member(ok, destination)

    def test_foreign_alias_stops_before_any_network_access(self):
        self.publish("3.12.14+20260924")
        self.paths.bin_dir.mkdir(parents=True)
        (self.paths.bin_dir / "python").write_text("#!/bin/sh\nexec /usr/bin/python3 \"$@\"\n")
        with self.assertRaisesRegex(mp.ManagerError, "--alias python=<new-name>"):
            self.install()
        self.assertEqual(self.net.calls, [])

    def test_rename_before_install_avoids_a_collision(self):
        self.publish("3.12.14+20260924")
        self.paths.bin_dir.mkdir(parents=True)
        uv = self.paths.bin_dir / "python3.12"
        uv.write_text("#!/bin/sh\nexec uv-python \"$@\"\n")
        mp.cmd_alias("python3.12=py312", self.paths)
        self.install()
        self.assertEqual(uv.read_text(), "#!/bin/sh\nexec uv-python \"$@\"\n")
        self.assertEqual(mp.alias_owner(self.paths.bin_dir / "py312"), "ours")

    def test_later_install_keeps_the_manager_version(self):
        self.publish("3.12.14+20260924")
        self.publish("3.13.15+20260924")
        self.install()
        self.make_source("0.4.0")
        self.install("3.13")
        self.assertEqual(self.pointer().self_version, "0.3.0")
        self.assertEqual(os.listdir(self.paths.manager_dir), ["0.3.0"])
        self.assertIn("Self-update is not yet available", self.err.getvalue())

    def test_missing_manager_copy_is_reinstalled(self):
        self.publish("3.12.14+20260924")
        self.install()
        shutil.rmtree(self.paths.manager_dir / "0.3.0")
        self.install()
        self.assertTrue((self.paths.manager_dir / "0.3.0" / "manage-python.py").is_file())

    def test_manager_needs_a_version_file(self):
        self.publish("3.12.14+20260924")
        (self.source / "VERSION").unlink()
        with self.assertRaisesRegex(mp.ManagerError, "does not hold a version"):
            self.install()

    def test_windows_layout(self):
        paths = self.windows_paths()
        self.publish("3.12.14+20260924", windows=True, triple="x86_64-pc-windows-msvc")
        self.install(paths=paths, triple="x86_64-pc-windows-msvc")
        runtime = paths.runtime_dir("3.12.14")
        self.assertTrue((runtime / "python" / "Lib" / "EXTERNALLY-MANAGED").is_file())
        self.assertTrue(all(p.is_file() for p in paths.pointer_files.values()))
        self.assertEqual(sorted(os.listdir(paths.bin_dir)), [
            "manage-python.cmd", "manage-python.ps1", "python.cmd", "python.ps1",
            "python3.12.cmd", "python3.12.ps1"])

    def test_path_notes(self):
        self.env["PATH"] = "/usr/bin"
        self.publish("3.12.14+20260924")
        self.install()
        self.assertIn("is not on your PATH", self.err.getvalue())


# ── --switch ──────────────────────────────────────────────────────────────────

class InstalledSet(Lifecycle):
    """3.12.13, 3.12.14 and 3.13.15 installed, 3.12.14 the default."""

    def setUp(self):
        super().setUp()
        for label in ("3.12.13+20260801", "3.12.14+20260924", "3.13.15+20260924"):
            self.publish(label)
        for label in ("3.12.13+20260801", "3.13.15+20260924", "3.12.14+20260924"):
            self.install(label)


class TestSwitch(InstalledSet):

    def test_switch_within_a_line(self):
        alias = (self.paths.bin_dir / "python3.12").read_bytes()
        mp.cmd_switch("3.12.13", self.paths)
        record = self.pointer()
        self.assertEqual((record.default, record.lines),
                         ("3.12.13", {"3.12": "3.12.13", "3.13": "3.13.15"}))
        self.assertEqual(record.self_version, "0.3.0")
        self.assertEqual((self.paths.bin_dir / "python3.12").read_bytes(), alias)

    def test_switch_across_lines_moves_python(self):
        mp.cmd_switch("3.13.15", self.paths)
        self.assertIn("3.13\n  aliases     python3.13  python\n", self.status())

    def test_keeps_renamed_aliases(self):
        mp.cmd_alias("python3.12=py312", self.paths)
        mp.cmd_switch("3.12.13", self.paths)
        self.assertEqual(self.pointer().alias_name("3.12"), "py312")
        self.assertFalse((self.paths.bin_dir / "python3.12").exists())

    def test_restores_a_missing_alias(self):
        (self.paths.bin_dir / "python").unlink()
        mp.cmd_switch("3.12.14", self.paths)
        self.assertEqual(mp.alias_owner(self.paths.bin_dir / "python"), "ours")

    def test_refusals(self):
        with self.assertRaisesRegex(mp.ManagerError, "--install 3.12.9"):
            mp.cmd_switch("3.12.9", self.paths)
        for bad in ("3.12", "0.3.0+1", "latest"):
            with self.subTest(bad=bad), self.assertRaises(mp.UsageError):
                mp.cmd_switch(bad, self.paths)


# ── --remove ──────────────────────────────────────────────────────────────────

class TestRemove(InstalledSet):

    def test_removes_an_unaliased_version(self):
        before = self.pointer()
        mp.cmd_remove("3.12.13", self.paths)
        self.assertFalse(self.paths.runtime_dir("3.12.13").exists())
        self.assertEqual(self.pointer(), before)
        self.assertIn("--install 3.12.13+20260801", self.err.getvalue())
        self.assertIn("virtual environments created with 3.12.13", self.err.getvalue())
        self.assertIn("    archived    3.12.13+20260801\n", self.status())
        self.assertEqual([e for e in self.share_entries() if e.startswith(".")], [])

    def test_refuses_the_default(self):
        with self.assertRaisesRegex(mp.ManagerError, "default version"):
            mp.cmd_remove("3.12.14", self.paths)
        self.assertTrue(self.paths.runtime_dir("3.12.14").is_dir())

    def test_refuses_a_line_version_while_others_remain(self):
        mp.cmd_switch("3.12.13", self.paths)
        mp.cmd_switch("3.13.15", self.paths)
        with self.assertRaisesRegex(mp.ManagerError, "--switch 3.12.14"):
            mp.cmd_remove("3.12.13", self.paths)

    def test_last_version_of_a_line_takes_its_alias(self):
        mp.cmd_alias("python3.13=py313", self.paths)
        mp.cmd_remove("3.13.15", self.paths)
        record = self.pointer()
        self.assertNotIn("3.13", record.lines)
        self.assertEqual(record.aliases.get("3.13"), "py313")
        self.assertFalse((self.paths.bin_dir / "py313").exists())
        self.publish("3.13.16+20261001")
        self.install("3.13.16+20261001")
        self.assertEqual(mp.alias_owner(self.paths.bin_dir / "py313"), "ours")

    def test_refusals(self):
        with self.assertRaisesRegex(mp.ManagerError, "not installed"):
            mp.cmd_remove("3.12.9", self.paths)
        with self.assertRaises(mp.UsageError):
            mp.cmd_remove("3.12", self.paths)


# ── --alias ───────────────────────────────────────────────────────────────────

class TestAliasCommand(InstalledSet):

    def test_rename_a_versioned_alias(self):
        mp.cmd_alias("python3.12=py312", self.paths)
        self.assertEqual(self.pointer().aliases["3.12"], "py312")
        self.assertFalse((self.paths.bin_dir / "python3.12").exists())
        self.assertIn("PYTHON_MANAGER_3_12", (self.paths.bin_dir / "py312").read_text())
        self.assertIn("  aliases     py312  python\n", self.status())
        mp.cmd_alias("py312=python3.12", self.paths)
        self.assertTrue((self.paths.bin_dir / "python3.12").exists())
        self.assertFalse((self.paths.bin_dir / "py312").exists())

    def test_rename_python_and_the_manager(self):
        mp.cmd_alias("python=py", self.paths)
        mp.cmd_alias("manage-python=mp", self.paths)
        self.assertIn("PYTHON_MANAGER_DEFAULT", (self.paths.bin_dir / "py").read_text())
        self.assertIn("PYTHON_MANAGER_SELF", (self.paths.bin_dir / "mp").read_text())
        self.assertFalse((self.paths.bin_dir / "manage-python").exists())

    def test_refuses_a_foreign_file(self):
        (self.paths.bin_dir / "py312").write_text("someone else's\n")
        before = self.pointer()
        with self.assertRaisesRegex(mp.ManagerError, "not written by manage-python"):
            mp.cmd_alias("python3.12=py312", self.paths)
        self.assertEqual(self.pointer(), before)
        self.assertTrue((self.paths.bin_dir / "python3.12").exists())

    def test_refuses_a_name_another_alias_uses(self):
        with self.assertRaisesRegex(mp.ManagerError, "used twice"):
            mp.cmd_alias("python3.12=python3.13", self.paths)

    def test_leaves_a_foreign_old_file_in_place(self):
        (self.paths.bin_dir / "python3.12").write_text("replaced by hand\n")
        mp.cmd_alias("python3.12=py312", self.paths)
        self.assertEqual((self.paths.bin_dir / "python3.12").read_text(), "replaced by hand\n")
        self.assertIn("left in place", self.err.getvalue())

    def test_refusals(self):
        with self.assertRaisesRegex(mp.ManagerError, "no alias named"):
            mp.cmd_alias("pip=p", self.paths)
        for spec in ("python", "=py", "python=", "python3.12=../x"):
            with self.subTest(spec=spec), self.assertRaises(mp.ManagerError):
                mp.cmd_alias(spec, self.paths)
        with self.assertRaises(mp.UsageError):
            mp.cmd_alias("python", self.paths)

    def test_same_name_is_a_no_op(self):
        before = self.pointer()
        mp.cmd_alias("python=python", self.paths)
        self.assertEqual(self.pointer(), before)


# ── main, exit codes and the operator log ─────────────────────────────────────

class TestMainLifecycle(InstalledSet):

    def run_main(self, *argv):
        with mock.patch.object(mp, "Paths", return_value=self.paths), \
             mock.patch.object(mp, "Network", return_value=self.net), \
             mock.patch.object(mp, "detect_triple", return_value=TRIPLE):
            return mp.main(list(argv))

    def log_lines(self):
        return self.paths.log_file.read_text().splitlines()

    def test_exit_codes_and_log(self):
        self.assertEqual(self.run_main("--switch", "3.12.13"), 0)
        self.assertEqual(self.run_main("--switch", "3.12"), 2)
        self.assertEqual(self.run_main("--remove", "3.12.9"), 1)
        self.assertEqual(self.run_main("--alias", "python=py"), 0)
        lines = self.log_lines()
        self.assertEqual(len(lines), 3)             # the usage error is not logged
        self.assertRegex(lines[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ switch 3\.12\.13 ok$")
        self.assertRegex(lines[1], r" remove 3\.12\.9 failed: 3\.12\.9 is not installed$")
        self.assertRegex(lines[2], r" alias py ok$")

    def test_install_through_main(self):
        self.publish("3.13.16+20261001")
        self.assertEqual(self.run_main("--install", "3.13.16+20261001"), 0)
        self.assertRegex(self.log_lines()[-1], r" install 3\.13\.16 ok$")

    @POSIX_ONLY
    def test_refuses_root(self):
        with mock.patch.object(mp.os, "geteuid", return_value=0):
            self.assertEqual(self.run_main("--switch", "3.12.13"), 1)
        self.assertIn("sudo", self.err.getvalue())
        self.assertEqual(self.pointer().default, "3.12.14")

    def test_status_is_read_only(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.run_main("--status"), 0)
        self.assertFalse(self.paths.log_file.exists())


if __name__ == "__main__":
    unittest.main()
