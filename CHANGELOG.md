# Changelog

All notable changes to osat-fluent-python-tool are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions track the `VERSIO
N` file and the git tags. Dates are ISO 8601.

## [Unreleased]

### Added

- `manage-python.py`, the 0.3.0 reference implementation of the layout and lifecycle proposal, starting with the parts that need no downloads: the pointer file and alias record in POSIX, `.cmd` and `.ps1` syntax with atomic writes; `PROVENANCE` read and write, sharing restic-tool's first five keys; platform triple selection with Rosetta and musl detection; `--status` built from the filesystem; and alias rendering with the `by:` ownership check. `--status` and `--version` are the only commands so far.
- Alias templates `scripts/nix/alias.template`, `scripts/windows/alias.cmd.template` and `scripts/windows/alias.ps1.template`, with restic-tool's header block.
- `test_manage_python.py`, offline `unittest` coverage for all of the above, including a real `/bin/sh` run of a rendered alias against a fake runtime.

## [0.2.0] - 2026-08-03

### Added

- File Fairy payload
