#!/usr/bin/env python3
# e2e_manage_python.py
"""
e2e_manage_python.py, end-to-end pass for manage-python.py against real
python-build-standalone runtimes, in a scratch home.

Installs two micro versions of one minor line and the latest of a second
line, then switches, renames, removes and restores from the archive with the
network unreachable, checking every alias, --status, the pip refusal, a venv
and the operator log along the way. The first install runs this checkout's
manage-python.py, which installs itself; everything after that runs through
the installed aliases, as a user would.

Isolation: HOME, the XDG variables, LOCALAPPDATA and APPDATA all point into
WORK/run, sandbox mode is on, and the real home's manager locations are
checked unchanged at the end.

Downloads are cached in WORK/cache (release lookups, SHA256SUMS and
tarballs), so a rerun downloads nothing. WORK/run is recreated on every run
and deleted after a pass; after a failure it is kept for inspection.

Usage:
    python3 e2e_manage_python.py --work DIR [--line 3.12] [--other 3.13] [--keep]
    python3 e2e_manage_python.py --work DIR --clean      delete DIR, cache included
"""

import argparse
import hashlib
import importlib.util
import json
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
SCRIPT = REPO / "manage-python.py"
DEAD_PROXY = "http://127.0.0.1:9"      # nothing listens here: any download fails at once


class Failed(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Failed(message)


# ── The manager, run in-process with a download cache ─────────────────────────

def run_as_manager(cache_dir, args):
    """Load this checkout's manage-python.py and run main(args) with a Network
    that answers from WORK/cache and fills it from the real network."""
    spec = importlib.util.spec_from_file_location("manage_python", SCRIPT)
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)

    class CachingNetwork(mp.Network):
        def _cached(self, url, suffix):
            return Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest()[:32] + suffix)

        def _record(self, url, kind):
            with open(Path(cache_dir) / "requests.log", "a") as handle:
                handle.write(f"{kind} {url}\n")

        def get_json(self, url):
            return json.loads(self.get_text(url))

        def get_text(self, url):
            path = self._cached(url, ".txt")
            if path.exists():
                self._record(url, "cached")
                return path.read_text(encoding="utf-8")
            text = super().get_text(url)
            path.write_text(text, encoding="utf-8")
            self._record(url, "fetched")
            return text

        def download(self, url, destination):
            path = self._cached(url, ".bin")
            if path.exists():
                self._record(url, "cached")
            else:
                super().download(url, path)
                self._record(url, "fetched")
            shutil.copyfile(path, destination)

    mp.Network = CachingNetwork
    return mp.main(args)


# ── The pass ──────────────────────────────────────────────────────────────────

class Pass:

    def __init__(self, work, line, other):
        self.work = Path(work).resolve()
        self.cache = self.work / "cache"
        self.run = self.work / "run"
        self.line, self.other = line, other
        self.env = {
            "PATH": f"{self.run / 'bin'}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "HOME": str(self.run / "home"),
            "XDG_DATA_HOME": str(self.run / "data"),
            "XDG_CONFIG_HOME": str(self.run / "config"),
            "XDG_STATE_HOME": str(self.run / "state"),
            "XDG_BIN_HOME": str(self.run / "bin"),
            "LOCALAPPDATA": str(self.run / "local"),
            "APPDATA": str(self.run / "roaming"),
            "PYTHON_MANAGER_SANDBOX": "1",
            "LANG": "C.UTF-8",
        }
        if os.environ.get("GITHUB_TOKEN"):
            self.env["GITHUB_TOKEN"] = os.environ["GITHUB_TOKEN"]
        self.offline = dict(self.env, https_proxy=DEAD_PROXY, HTTPS_PROXY=DEAD_PROXY,
                            http_proxy=DEAD_PROXY, HTTP_PROXY=DEAD_PROXY, PIP_NO_INDEX="1")
        self.real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)

    # ── helpers ──

    def sh(self, *argv, env=None, expect=0):
        result = subprocess.run([str(a) for a in argv], env=env or self.offline,
                                capture_output=True, text=True, timeout=600)
        shown = " ".join(str(a) for a in argv).replace(str(self.run), "$RUN")
        if expect is not None and result.returncode != expect:
            raise Failed(f"{shown} exited {result.returncode}, expected {expect}\n"
                         f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def bootstrap(self, *args):
        """This checkout's manager, the downloaded release, with the cache."""
        return self.sh(sys.executable, __file__, "--as-manager", self.cache, "--", *args, env=self.env)

    def manage(self, *args, expect=0):
        """The installed manager, through its alias, with no network."""
        return self.sh(self.run / "bin" / "manage-python", *args, expect=expect)

    def version_of(self, alias):
        out = self.sh(self.run / "bin" / alias, "--version").stdout.strip()
        check(out.startswith("Python "), f"{alias} --version printed {out!r}")
        return out.split()[1]

    def pointer(self):
        text = (self.run / "config" / "python-manager" / "python-manager.env").read_text()
        values = {}
        for line in text.splitlines():
            if line.startswith("PYTHON_MANAGER_"):
                key, value = line.split("=", 1)
                values[key] = value.strip('"')
        return values

    def status(self):
        return self.manage("--status").stdout

    def step(self, name):
        print(f"[e2e] {name}", flush=True)

    def real_home_snapshot(self):
        places = [".local/share/python-manager", ".config/python-manager", ".local/state/python-manager",
                  ".local/bin/python", ".local/bin/python3.12", ".local/bin/python3.13",
                  ".local/bin/manage-python", ".local/bin/py312"]
        snapshot = {}
        for place in places:
            path = self.real_home / place
            snapshot[place] = path.lstat().st_mtime_ns if os.path.lexists(path) else None
        return snapshot

    # ── the scenario ──

    def execute(self):
        for value in (self.run, self.cache):
            check(not str(value).startswith(str(self.real_home) + os.sep),
                  f"--work must be outside the real home ({self.real_home})")
        if self.run.exists():
            shutil.rmtree(self.run)
        self.run.mkdir(parents=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        before = self.real_home_snapshot()
        started = time.time()

        self.step(f"install {self.line} with this checkout's manager")
        self.bootstrap("--install", self.line)
        newest = self.pointer()["PYTHON_MANAGER_DEFAULT"]
        check(newest.startswith(self.line + "."), f"installed {newest}, not a {self.line} version")
        major, minor, micro = (int(p) for p in newest.split("."))
        check(micro > 0, f"{newest} has no earlier micro version to install")
        older = f"{major}.{minor}.{micro - 1}"
        line_alias = f"python{self.line}"
        check(self.version_of("python") == newest, "python does not run the new install")
        check(self.version_of(line_alias) == newest, f"{line_alias} does not run {newest}")
        manager = self.pointer()["PYTHON_MANAGER_SELF"]
        first = self.status().splitlines()[0]
        check(first == f"manage-python {manager}", f"--status starts with {first!r}")
        installed_copy = self.run / "data" / "python-manager" / "manage-python" / manager
        check((installed_copy / "VERSION").read_text().strip() == manager, "installed VERSION differs")

        self.step(f"install {self.other}; {line_alias} stays on {newest}")
        self.bootstrap("--install", self.other)
        other = self.pointer()["PYTHON_MANAGER_DEFAULT"]
        check(other.startswith(self.other + "."), f"installed {other}")
        check(self.version_of("python") == other, "python did not move to the new line")
        check(self.version_of(f"python{self.other}") == other, "the second line's alias is wrong")
        check(self.version_of(line_alias) == newest, f"{line_alias} moved")

        self.step(f"install {older} by full version (release search)")
        self.bootstrap("--install", older)
        check(self.version_of("python") == older, "python does not run the older micro version")
        check(self.version_of(line_alias) == older, f"{line_alias} does not run {older}")

        self.step(f"switch to {newest} through the installed manager")
        self.manage("--switch", newest)
        check(self.version_of("python") == newest, "switch did not move python")
        check(self.version_of(line_alias) == newest, f"switch did not move {line_alias}")
        check(self.version_of(f"python{self.other}") == other, "switch moved the other line")

        self.step(f"rename {line_alias} to py312, then switch and install again")
        self.manage("--alias", f"{line_alias}=py312")
        check(not (self.run / "bin" / line_alias).exists(), f"{line_alias} was left behind")
        check(self.version_of("py312") == newest, "py312 does not run the default")
        self.manage("--switch", older)
        check(self.version_of("py312") == older, "py312 did not follow the switch")
        self.bootstrap("--install", newest)
        check(self.version_of("py312") == newest, "py312 did not follow the install")
        check(not (self.run / "bin" / line_alias).exists(), "the rename was lost on install")
        status = self.status()
        check(f"  aliases     py312  python\n    default     {newest}\n    installed   {older}\n"
              in status, f"--status does not show the rename:\n{status}")

        self.step("pip refuses the installed runtime; a venv works")
        refused = self.sh(self.run / "bin" / "python", "-m", "pip", "install", "--dry-run", "six",
                          expect=None)
        check(refused.returncode != 0 and "externally-managed-environment" in refused.stderr,
              f"pip was not refused:\n{refused.stdout}{refused.stderr}")
        venv = self.run / "venv"
        self.sh(self.run / "bin" / "py312", "-m", "venv", venv)
        check(self.sh(venv / "bin" / "python", "--version").stdout.split()[1] == newest,
              "the venv runs a different version")
        self.sh(venv / "bin" / "python", "-m", "pip", "--version")

        self.step(f"remove {older}; the default is refused")
        self.manage("--remove", newest, expect=1)
        self.manage("--remove", older)
        runtime = self.run / "data" / "python-manager" / older
        check(not runtime.exists(), f"{older} is still on disk")
        status = self.status()
        check(f"    archived    {older}+" in status, f"{older} is not listed as archived:\n{status}")

        self.step(f"restore {older} from the archive with the network unreachable")
        self.manage("--install", older)
        provenance = (runtime / "PROVENANCE").read_text()
        check("source: local archive (" in provenance, f"not restored from the archive:\n{provenance}")
        check(self.version_of("python") == older, "the restored runtime does not run")
        check((runtime / "python" / "lib" / f"python{self.line}" / "EXTERNALLY-MANAGED").is_file(),
              "the restored runtime is not protected")

        self.step("operator log, file modes and the real home")
        log = (self.run / "state" / "python-manager" / "manage-python.log").read_text().splitlines()
        actions = [line.split()[1:] for line in log]
        check([a[0] for a in actions] == ["install", "install", "install", "switch", "alias", "switch",
                                         "install", "remove", "remove", "install"],
              f"unexpected log:\n" + "\n".join(log))
        check(actions[7][2:4] == ["failed:", newest] and all(a[2] == "ok" for i, a in
                                                           enumerate(actions) if i != 7),
              "log results are wrong:\n" + "\n".join(log))
        # Everything the manager writes is owner-only. Inside a runtime that
        # means its directory, PROVENANCE and EXTERNALLY-MANAGED: the runtime
        # later writes __pycache__ with the user's umask, unreachable to others
        # because the runtime directory itself is 0700.
        share = self.run / "data" / "python-manager"
        written = [share, *share.iterdir()]
        for root in (share / "archive", share / "manage-python", self.run / "config" / "python-manager",
                     self.run / "state" / "python-manager"):
            written += [root, *root.rglob("*")]
        for version in (newest, older, other):
            written += [share / version / "PROVENANCE",
                        *(share / version / "python" / "lib").glob("python3.*/EXTERNALLY-MANAGED")]
        for path in written:
            if not path.is_symlink():
                check(path.stat().st_mode & 0o077 == 0, f"{path} is not owner-only")
        check(self.real_home_snapshot() == before, "something changed in the real home")

        requests = (self.cache / "requests.log").read_text().splitlines()
        fetched = [r for r in requests if r.startswith("fetched")]
        print(f"[e2e] PASS in {time.time() - started:.0f}s: {newest}, {older} and {other} "
              f"on manager {manager}; {len(fetched)} of {len(requests)} requests fetched, "
              f"the rest from the cache")


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--as-manager":
        return run_as_manager(sys.argv[2], sys.argv[sys.argv.index("--") + 1:])
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", required=True, help="scratch directory: cache and run area")
    parser.add_argument("--line", default="3.12", help="minor line installed twice (default 3.12)")
    parser.add_argument("--other", default="3.13", help="second minor line (default 3.13)")
    parser.add_argument("--keep", action="store_true", help="keep WORK/run after a pass")
    parser.add_argument("--clean", action="store_true", help="delete WORK, cache included, and exit")
    args = parser.parse_args()
    work = Path(args.work)
    if args.clean:
        shutil.rmtree(work, ignore_errors=True)
        print(f"[e2e] removed {work}")
        return 0
    run = Pass(work, args.line, args.other)
    if (run.cache / "requests.log").exists():
        (run.cache / "requests.log").unlink()
    try:
        run.execute()
    except Failed as failure:
        print(f"[e2e] FAIL: {failure}\n[e2e] kept for inspection: {run.run}", file=sys.stderr)
        return 1
    if not args.keep:
        shutil.rmtree(run.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
