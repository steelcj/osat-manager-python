# Changelog

All notable changes to osat-fluent-python-tool are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions track the `VERSIO
N` file and the git tags. Dates are ISO 8601.

## [Unreleased]

### Fixed

- `install.ps1` failed with "Get-FileHash is not recognized" when Windows PowerShell 5.1 was started from a Command Prompt opened inside PowerShell 7: 5.1 inherits PowerShell 7's `PSModulePath` and cannot load `Get-FileHash`, a script-defined cmdlet. It now computes the SHA-256 with .NET. Found on the Windows 11 VM.

- Release archives no longer contain `.claude/` (session logs and assistant notes). They were in the 1.0.0 and 1.0.2 archives because those files were tracked, and `git archive`, which `publish-release.py` uses, packages every tracked file; `.gitignore` does not affect files that are already tracked. `.claude/` is no longer tracked (the files stay on disk; the root `CLAUDE.md` stays tracked), and `publish-release.py` now refuses to package a tag in which any tracked file matches `.gitignore`, naming the files, with a test in `test_publish_release.py`.

- On Windows the test suite failed (11 failures, 50 errors): the temporary directory, `%LOCALAPPDATA%\Temp`, is inside the user's home, and sandbox mode refused anything inside the real home, the suite's own scratch home included. Sandbox mode now refuses only the real locations the manager writes to outside sandbox mode, resolved from the system: on Windows `%LOCALAPPDATA%\python-manager`, `%LOCALAPPDATA%\Programs` and `%APPDATA%\python-manager` (and never the registry), on Linux and macOS `~/.local/share/python-manager`, `~/.config/python-manager`, `~/.local/state/python-manager` and `~/.local/bin`. Removing a tree that contains one of them is refused too. Found on the Windows 11 VM.

- Permission checks now follow the machine rather than the layout in use, so an existing directory is no longer refused as broader than owner-only on Windows, where every directory reports mode 0o777.

- The test suite runs on Windows: path separators, file encodings and symbolic links are handled portably, and on Windows the install tests read the version their stand-in interpreter scripts would print, since Windows cannot run them.

### Added

- The plain-language guide *Installing manage-python on Windows with Command Prompt*, version 0.1.2, in `en/docs/guides/osat-manager-python/`.

### Changed

- `validate-windows.ps1` reads the Windows version from the registry instead of `Get-CimInstance`, for the same reason, and adds section 11: `install.ps1` run from a Command Prompt opened inside PowerShell 7. The Windows validation instructions are at 0.2.0, with manual step M6 for machines without PowerShell 7.
- A unit test keeps `install.ps1`, `validate-windows.ps1` and the `.ps1` alias templates to cmdlets built into Windows PowerShell 5.1.

## [1.0.2] - 2026-09-29

Verified end to end on Linux x86-64. Not yet verified: on Windows, the registry write, the `.cmd` and `.ps1` aliases and `install.ps1`; macOS; Python 3.8 at run time. The Linux end-to-end pass ran on the code tagged 1.0.1; 1.0.2 changes only the Windows PATH code, which is covered by unit tests.

First published release of the 1.0.1 changes below, since 1.0.1 was never released. Supersedes 1.0.0, whose `install.sh` and `install.ps1` still ran the 0.2.0 installer, `install-python.py`.

### Changed

- The Windows user PATH change is visible and reversible. When `--install` actually changes it, the previous `Path` value and its registry type are saved to `path-backup-<UTC>.txt` in the state directory first, the change is announced on standard error with how to undo it, and a `path` line is logged. When the entry is already present nothing is printed or logged. A failed write is logged as `failed` and reported, and no longer fails the install.

## [1.0.1] - 2026-09-29

Tagged locally but never pushed or released; these changes were first published in 1.0.2.

Verified end to end on Linux x86-64. Not yet verified: the Windows registry write, the `.cmd` and `.ps1` aliases, `install.ps1`, macOS, and Python 3.8 at run time. Supersedes 1.0.0, whose `install.sh` and `install.ps1` still ran the 0.2.0 installer, `install-python.py`.

### Added

- Sandbox mode (`PYTHON_MANAGER_SANDBOX`) for tests, smoke runs and end-to-end runs: changing commands refuse to run unless HOME and the XDG variables (LOCALAPPDATA and APPDATA for Windows) are set and lie outside the account's real home, and every file write refuses a path inside the real home. The test suite turns it on and moves HOME and XDG to a scratch directory before anything runs.
- `--lang` and `PYTHON_MANAGER_LANG`, chosen in the proposal's order: the option, the variable, the system locale, then English. English is the only language for now; a requested language without a catalog falls back to English with a warning.
- On Windows, `--install` prepends `%LOCALAPPDATA%\Programs` to the user PATH in `HKCU\Environment`, keeping the value's registry type, only when it is not already there, and broadcasts `WM_SETTINGCHANGE`.
- `e2e_manage_python.py`, the scripted end-to-end pass: two micro versions of one minor line and one of another, installed, switched, renamed, removed and restored offline from the archive, in a scratch home with a download cache.

### Changed

- A first `--install` with no SPEC takes the newest stable minor line in the latest python-build-standalone release. Pre-release (alpha, beta, rc) and free-threaded builds are never selected.
- `--status` starts with a line naming the manager's alias and the version it runs.
- `install.sh` and `install.ps1` run `manage-python.py`, with `--install` when given no arguments, and check that the manager's `VERSION` and alias templates are beside it.
- The proposal is now at 0.7.0; the 0.5.1 and 0.6.0 versions are removed from `en/docs/`.
- README.md describes 1.0.x as the current release, links the 0.7.0 proposal, says what is verified, and points its links at `en/docs/`.

## [1.0.0] - 2026-09-29

### Added

- `manage-python.py`, the 0.3.0 reference implementation of the layout and lifecycle proposal, starting with the parts that need no downloads: the pointer file and alias record in POSIX, `.cmd` and `.ps1` syntax with atomic writes; `PROVENANCE` read and write, sharing restic-tool's first five keys; platform triple selection with Rosetta and musl detection; `--status` built from the filesystem; and alias rendering with the `by:` ownership check. Then `--install`, `--switch`, `--remove` and `--alias`: archive-first installs verified against SHA256SUMS, health-checked in a staging directory, protected with `EXTERNALLY-MANAGED` and archived; the manager installs itself under `manage-python/<version>/` and is reached through its own alias; each lifecycle action is logged to `manage-python.log`.
- Alias templates `scripts/nix/alias.template`, `scripts/windows/alias.cmd.template` and `scripts/windows/alias.ps1.template`, with restic-tool's header block.
- Manager alias templates `scripts/nix/manager-alias.template`, `scripts/windows/manager-alias.cmd.template` and `scripts/windows/manager-alias.ps1.template`, and the `PYTHON_MANAGER_SELF` and `PYTHON_MANAGER_ALIAS_SELF` pointer keys they read.
- `test_manage_python.py`, offline `unittest` coverage for all of the above, including real `/bin/sh` runs of rendered aliases against fake runtimes, and offline installs from generated tarballs through a fake network.

### Changed

- `manage-python.py` reads its version from the `VERSION` file beside it, and the installed copy carries its own `VERSION`; the version constant is gone.
- The `.ps1` aliases snapshot the session environment and restore it in a `finally` block, so the pointer's and operator environment's variables no longer leak into the calling PowerShell session. The Windows aliases stop with a message when their pointer key is unset.

## [0.2.0] - 2026-08-03

### Added

- File Fairy payload
