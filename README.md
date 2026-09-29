# osat-manager-python

Formerly osat-fluent-python-tool.

A governed OSAT Fluent manager that installs self-contained CPython runtimes into user space and lets you switch between them, with no elevated privilege, no package manager and no compiler required.

## Status

**0.2.0, current release.** An installer, run as `install-python.py`, that installs one CPython runtime per minor version and writes a versioned wrapper such as `python3.12`. Documented in [docs/en/README.md](docs/en/README.md). Tested end to end on Linux and on Windows 11.

**0.3.0, in development.** The first release as a full manager, run as `manage-python`. It keeps versions side by side and switches between them, adds a generic `python` alias alongside the versioned ones, lets any alias be renamed, protects installed runtimes from accidental package installs, keeps a verified archive for offline restores, and installs itself so it works from any directory. The design is set out in the [proposal](docs/en/proposal--osat-manager-python-layout-and-lifecycle-v0-5-0.md).

## About the rename

This repository was renamed from osat-fluent-python-tool as part of the OSAT collection's move from `-tool` installers to `-manager` implementations. Links to the old name redirect here.

If you have a local clone, point it at the new name:

```bash
git remote set-url origin https://github.com/steelcj/osat-manager-python.git
```

GitHub names its generated source archives after the repository, so the source zip for 0.2.0 now extracts to `osat-manager-python-0.2.0` rather than `osat-fluent-python-tool-0.2.0`. The contents are the same.

## Languages

- [English](docs/en/README.md)
