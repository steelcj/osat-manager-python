# Changelog

All notable changes to osat-fluent-python-tool are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions track the `VERSIO
N` file and the git tags. Dates are ISO 8601.

## [Unreleased]

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
