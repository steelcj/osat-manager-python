# End of Session Summary

Date: 2026-09-29T18:05:43-04:00

Your six decisions are implemented, the isolation guard is in, and the approved end-to-end pass succeeded on this machine with real runtimes. Nothing from this session is committed.

**The release you cut is 1.0.0, not 0.3.0.** `VERSION` is 1.0.0, `main` is in sync with origin, and the release commit is tagged `v1.0.0`; I didn't check whether the tag itself reached the remote. The installed manager now reports `manage-python 1.0.0`, while the README, the proposal and your note say 0.3.0. Your workflow says tags are never reused, so whether to keep 1.0.0 or move on to a later version is your call. I haven't changed anything.

## Isolation

- **Sandbox mode:** setting `PYTHON_MANAGER_SANDBOX` turns it on. Changing commands then refuse unless HOME and every XDG variable (LOCALAPPDATA and APPDATA when simulating Windows) are set and lie outside your real home. The real home is read from the system, not from `$HOME`.
- **Write guard:** every function that writes refuses any path inside the real home, including one reached through a symlink.
- **Where it's on:** the test module turns sandbox mode on and moves HOME and the XDG variables to scratch before the manager loads. The end-to-end runner does the same.
- **Last session's stray log line:** there's now a test for that exact scenario. The same run writes nothing into the home.

## Decisions

- **#18:** a first install with no SPEC takes the newest stable minor line. Pre-release and free-threaded builds are excluded everywhere by one named rule, and each exclusion has its own tests.
- **#27:** the Windows PATH prepend keeps the registry value's type and broadcasts `WM_SETTINGCHANGE`. The string logic and a fake registry are tested; the real registry write still needs your VM. In sandbox mode it never touches the registry.
- **#35:** `--status` now starts with `manage-python 1.0.0`, and a renamed manager alias shows its new name.
- **#38:** `--lang` and `PYTHON_MANAGER_LANG` are chosen in the proposal's order, with English only. A test uses a compiled French catalog to prove translation works.
- **#39:** `install.sh` and `install.ps1` now run `manage-python.py`, with `--install` when given no arguments. `install.sh` parses, and I confirmed it refuses before downloading when files are missing. Neither has been run through a full bootstrap.

## Tests

- **Unit tests:** 194 pass, one skipped because `pwsh` isn't installed.
- **Mutation check:** in a scratch copy I disabled each new guard and exclusion; each change makes the suite fail. At first the free-threaded exclusion didn't fail anything, because the exact asset-name match already rejected those names. It is now a separate rule with its own test.

## End-to-end pass

Linux x86-64, CPython 3.12.14, 3.12.13 and 3.13.15.

- **What it covered:** install, the full-version release search, switch, rename (kept across a later switch and install), the pip refusal, a venv, and remove with the default refused.
- **Offline restore:** it ran through the installed `manage-python` alias with the network deliberately made unreachable, and succeeded.
- **Log and real home:** the operator log was checked line by line, and the real home was unchanged.
- **Rerun and cleanup:** a rerun passed in 8 seconds with no downloads, since everything came from the cache. The scratch area is deleted.
- **One check I narrowed:** the first run failed only my own check that every file under a runtime is owner-only. The runtime later writes `__pycache__` with the user's umask, which is harmless because each runtime directory is 0700. The check now covers only what the manager writes.

## Further differences from proposal 0.6.0

40. **Sandbox mode** and its variable, `PYTHON_MANAGER_SANDBOX`, are new.
41. **First install with no SPEC** takes the newest stable minor line in the latest release.
42. **Pre-release and free-threaded builds** (any asset name containing "freethreaded") are never selected, and a SPEC can't name a pre-release. The proposal names only the `install_only_stripped` flavour.
43. **Alias check timing:** on a first install with no SPEC, the new line's alias is checked after the release lookup but before any download. All other aliases are checked before any network access.
44. **`--status` first line** is `<manager alias> <SELF version>`, or `not installed`, followed by a blank line.
45. **`--lang` details:**
    - an invalid code is a usage error (exit 2)
    - an unavailable `--lang` or `PYTHON_MANAGER_LANG` falls back to English with a warning; an unavailable system locale falls back silently
    - `fr_CA` falls back to `fr`
    - `PYTHON_MANAGER_LANG` is read from the process environment, so the POSIX operator `env` file must `export` it
    - the Windows system language is the user's display language
46. **No catalog files yet:** English is built in as the source language, with no `.pot`, `.po` or `.mo` files. The proposal describes `locale/manage-python.pot` and a `.po` per language.
47. **Windows PATH details:**
    - `REG_EXPAND_SZ` gets `%LOCALAPPDATA%\Programs` unexpanded, and `REG_SZ` gets the expanded path
    - a missing value is created as `REG_EXPAND_SZ`
    - duplicates are detected after expansion, ignoring case, slashes, trailing backslashes and quotes
    - empty `;;` entries are dropped on rewrite
    - other value types are refused
    - it runs on every Windows `--install`, doing nothing if the entry is present, and is skipped in sandbox mode
    - it wins over the Microsoft Store alias, which is also in the user PATH, but the system PATH still comes first
48. **Bootstrap scripts** default to `--install` and check for `VERSION` and the alias templates. They still use CPython 3.11.13 pinned for x86-64 and ARM64 glibc and macOS on POSIX, and x86-64 only for `install.ps1`, with nothing for musl or Windows ARM64.
49. **Owner-only permissions** cover what the manager writes. The runtime's own later writes, such as `__pycache__`, follow the user's umask inside a 0700 runtime directory. This refines #28.

## Still unverified

- The Windows registry write and broadcast, all `.cmd` and `.ps1` aliases, and `install.ps1`.
- A full `install.sh` bootstrap, which downloads its own pinned Python.
- The PowerShell environment test.
- macOS.
- Python 3.8 at runtime.

## Choices for you

Whether to keep the 1.0.0 version, and whether to commit this session's work.
