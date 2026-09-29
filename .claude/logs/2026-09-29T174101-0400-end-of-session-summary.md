# End of Session Summary

Date: 2026-09-29T17:41:01-04:00

`manage-python.py` now has `--install`, `--switch`, `--remove` and `--alias`, and your three decisions are implemented. All 157 unit tests pass, with one skipped: the PowerShell environment test, because `pwsh` isn't installed here. Nothing downloaded a runtime and no end-to-end pass has run; every install test uses small generated tarballs through a fake network. Nothing is committed.

To check the tests catch real regressions, I disabled four safety checks one at a time in a scratch copy: the alias pre-flight, the health check, the refusal to remove the default, and verification of archived tarballs. Each change made the suite fail.

## Your three decisions

- **Manager alias:** implemented with `PYTHON_MANAGER_SELF` and `PYTHON_MANAGER_ALIAS_SELF`, using your exec line with the `:?` guard on both keys, plus `.cmd` and `.ps1` equivalents. A test runs the real alias against a fake runtime. `--switch` never changes `SELF`.
- **`.ps1` leak:** both `.ps1` templates now snapshot the environment, restore changed variables and remove added ones in `finally`, then `exit $osatExit`. The pointer's `.ps1` syntax is unchanged. The PowerShell test is written but has never run.
- **Version source:** `VERSION` is the only source and the constant is gone. The installed copy gets its own `VERSION`. `--version` now prints 0.2.0 in this checkout until you cut 0.3.0.

One incident: a read-only smoke test of `--switch 3.12` wrote a log line to your real `~/.local/state/python-manager/`. I deleted the file and the directory, which held only that line. Usage errors (exit code 2) are now not logged at all.

## Differences from proposal 0.6.0, for 0.6.1

### Pointer file

1. Adds `PYTHON_MANAGER_SELF` and `PYTHON_MANAGER_ALIAS_SELF`. `SELF` comes after the version keys, and `ALIAS_SELF` is the last alias key.
2. Starts with `#`/`rem` comment lines naming the file and the operator environment, as restic-tool does, and puts a blank line before the alias keys. The contract says the file holds "only `PYTHON_MANAGER_*` keys".
3. Keeps unknown `PYTHON_MANAGER_*` keys when it rewrites the file.
4. Validation rules the proposal doesn't state:
   - values are limited to letters, digits and `._+-`
   - `DEFAULT` must equal its minor line's version
   - alias names are 1–64 characters and can't be Windows device names (NUL, CON, …) or end in `.cmd`, `.ps1`, `.exe` or `.bat`
   - alias names must be unique, ignoring case
   - `manage-python` is reserved for the manager's own alias
5. A renamed alias keeps its name record even when its minor line has no version, for example `ALIAS_3_13` without `PYTHON_MANAGER_3_13`.

### Aliases

6. The POSIX aliases use a `${…:?}` guard.
7. The Windows `.cmd` aliases use `if not defined … goto :unset` and then `exit /b %ERRORLEVEL%`. The runtime is no longer the last command, but its exit code is still what the alias returns. The contract wording ("exit code of its last command") needs updating.
8. The `.cmd` header starts with a bare `rem` line.
9. The `.ps1` aliases use snapshot and restore, `throw` when their key is unset, and `exit $osatExit`. The proposal shows no `.ps1` alias at all.
10. There are six templates, not the two the proposal names: `alias.ps1.template` and three `manager-alias.*` templates are added. Their comment blocks are longer than the proposal's example.
11. The manager alias defines `_share` alongside `_cfg`.
12. The rendered `path:` line shows the real location: `~` or `%LOCALAPPDATA%`, respecting XDG overrides.
13. Ownership rules: symlinks, binaries and unreadable files count as someone else's, and the `by:` line only counts inside the header's `generated` section.

### The manager itself

14. `manage-python/<version>/` holds `manage-python.py`, `VERSION`, `scripts/` (the six templates), `locale/` when present, and `PROVENANCE`. The proposal lists only the script, `locale/` and `PROVENANCE`.
15. The manager's `PROVENANCE` has `asset: manage-python.py`, the script's SHA-256, and `source: local copy (<path>)`. That third source form isn't in the contract.
16. The manager installs itself during `--install` when `SELF` is unset or its directory is missing. A newer manager running a later install leaves `SELF` alone and logs that self-update isn't available yet.
17. Runtime `PROVENANCE` records the version of the manager that installed it.

### `--install`

18. With no SPEC it installs the latest of the current default's minor line, or 3.12 on a first install. The proposal doesn't define the first-install case.
19. A full version such as `3.12.14` comes from the archive first (newest build). Otherwise it searches the most recent 150 releases (5 pages of 30).
20. A version already installed is switched to without downloading, even when a different build was requested.
21. Every alias the install will write is checked for ownership before any network access.
22. Archive entries are `archive/<v>+<build>/`, holding the tarball and a `PROVENANCE` that records its checksum. Restoring from the archive re-verifies the tarball and refuses on a mismatch.
23. Work happens in hidden `.staging-*`, `.download-*` and `.removing-*` directories inside the share directory, and is renamed into place so a failure leaves nothing behind.
24. `EXTERNALLY-MANAGED` goes in `python/lib/python3.X/` (`python/Lib/` on Windows). Its message always says `python3.X -m venv .venv`, even if that alias is renamed.
25. A health-check failure mentions nix-ld for NixOS.
26. `GITHUB_TOKEN` is sent to api.github.com only. A rate-limit error suggests a pinned build, which needs no API call.
27. **Not implemented:** prepending `%LOCALAPPDATA%\Programs` to the Windows user PATH. The manager prints advice instead.
28. Runtime, archive and manager directories are owner-only.

### `--remove`

29. Removing the last installed version of a non-default minor line also removes that line's pointer key and alias files. A renamed alias name is kept for the next install.
30. **Proposal gap:** there's no way to change which version a minor line's alias runs without also moving `python`, because `--switch` always moves both. Removing a line's current version while others are installed is refused, and the refusal suggests two switches.
31. The runtime directory is renamed aside before deletion, so a failed removal never leaves a half-deleted runtime.

### `--alias`

32. OLD is the alias's current name. For an alias not yet written, OLD can be its default name, so a clash can be avoided before the first install.
33. Old alias files are removed only if the manager wrote them; anyone else's are left in place with a warning.

### Output and logging

34. Log lines are `<UTC> <action> <version> ok|failed: <message>`. For `--alias`, the logged value is the new name. Usage errors aren't logged.
35. `--status` warns when `SELF` isn't installed or an alias file is missing. It doesn't show the manager alias.
36. Actions are mutually exclusive, and running with no action prints usage and exits 2.
37. Changing commands refuse to run as root or Administrator, as `install-python.py` did. The proposal doesn't mention this.
38. **Not implemented:** `--lang` and translation catalogs. Messages go through gettext unchanged.
39. **Not updated:** `install.sh` and `install.ps1` still run `install-python.py`.

## Still unverified

- Anything against real python-build-standalone downloads.
- Python 3.8 at runtime (the files only pass the 3.8 grammar check).
- Every Windows template. Nothing here has run a `.cmd` or `.ps1`, including the new guards, `exit /b %ERRORLEVEL%`, and the environment restore.
- macOS.

## Choices for you

- **Commit:** your workflow as last time, as a normal commit with no release cut.
- **End-to-end pass:** download two real 3.12 runtimes and one 3.13 runtime (roughly 100 MB total) into a scratch home, then run install, switch, rename, remove and offline restore.
