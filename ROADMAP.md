# ROADMAP

## Open items

### Bug 001

One small manager bug turned up while testing. The refusal message prints a lone `.` line before `python3.14 -m venv .venv`. That's the Debian control-file convention for a blank line, but pip prints it literally. Removing it from the `EXTERNALLY_MANAGED` text in `manage-python.py` would clean up the message. I left it out of the guide's shortened output.

#### Fix

The fix is a one-line change to the `EXTERNALLY_MANAGED` string in `manage-python.py` (around line 1421): delete the ` .` line.

```python
EXTERNALLY_MANAGED = """[externally-managed]
Error=This Python runtime is managed by manage-python and does not accept
 package installs, so it stays intact for every virtual environment built on it.
 Create a virtual environment and install into that instead:
     python{minor} -m venv .venv
"""
```

A unit test that reads the written `EXTERNALLY-MANAGED` file back with `configparser` could also check that no line of the `Error` value is only `.`. That would stop it from coming back. Once it's fixed, the shortened refusal output in the latest-release guide stays accurate as it is.

### Translations

In order to ensure that translations are working we should add fr-ca translations and perhaps spanish as well in order to ensure that everything is functioning as it should. This may be less important for geeky python people but more important over time as we add more universal cake metric features.

### osat-fluent variances

#### install-<target>.py

Fluent "install" scripts are actually manage scripts. Options should be similar/unified so expectations are the same. 

###### example of install-restic.py

```bash
Usage:
    install-restic.py --install [VERSION]  Install a version (default: latest)
    install-restic.py --switch VERSION     Point the env file at an installed version
    install-restic.py --status             Show installed, archived, and active versions
    install-restic.py --remove VERSION     Remove an installed version (archive is kept)
    install-restic.py --version            Show this manager's version

```

yet for `install-python.py` `--version` is replaced with `--track`

In addition Fluent some tools use the "tool" postfix to differentiate  (<tool_name>-tool) from system apps with the same name. Yet the python-tool uses the "track" (version) postfix. This might be good or bad, the point is that it is different and we should have a good reason that is explained as to why this is the case.

### Windows: install-python.py and install.ps1 both untested on real hardware.

The platform detection (`x86_64-pc-windows-msvc`), versioned-layout paths, and both wrapper templates are written. `install.ps1` additionally parses cleanly under PowerShell 7's own AST parser and its checksum logic (`Get-FileHash`) has been verified to produce output identical to `sha256sum`, but neither script has been run end-to-end on an actual Windows machine. Do not treat Windows support as verified until that happens.

### macOS: install-python.py untested on real hardware.

Same caveat as Windows, minus the wrapper format question (macOS uses the nix wrapper template and `install.sh`, both already proven end-to-end on Linux with zero Python or bash present). The `x86_64-apple-darwin` and `aarch64-apple-darwin` target triples themselves have not been exercised against a real download on real macOS hardware.

**musl libc not wired up.** `TARGET_TRIPLES` only maps to glibc targets on Linux (`x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`). Alpine and other musl-based systems will fail with the "unsupported platform" error even though python-build-standalone does publish musl builds. Add musl detection (e.g. via `platform.libc_ver()` or checking for the presence of `/etc/alpine-release`) and the corresponding target triples if this becomes a real need.

**`GITHUB_TOKEN` support exists but is undocumented.** The installer already sends a bearer-adjacent higher-limit path via the GitHub API when rate-limited advice is given in the error message, but there is no documentation anywhere telling a person how or why they'd set it. Add a section to docs/en/README.md once this is confirmed worth documenting (it may not come up often enough to be worth the complexity).

**No `--list` or `--uninstall` command yet.** Every other Fluent tool in this fleet eventually needs a way to see what's installed and remove a version cleanly. python-tool doesn't have either yet; for now, removal is manual (`rm -rf` the version directory and the wrapper).

**Bootstrap scripts are pinned to a fixed release (tag `20250828`, CPython 3.11.13).** This is deliberate, the bootstrap Python is disposable and only needs to run `install-python.py`, which does its own current release lookup for the real, permanent install, but the pin will eventually be old enough to be worth a policy decision: update it periodically, or leave it alone indefinitely since its only job never changes. Not urgent.

## Deliberately out of scope

**Package installation beyond the interpreter itself.** python-tool installs CPython, `pip`, and `venv`. It does not manage project dependencies, virtual environments, or package installation beyond what ships in the base python-build-standalone artifact. That's a different tool's job.

**Non-glibc, non-musl Linux C libraries.** Anything outside the two libc families python-build-standalone itself supports is out of scope here; we inherit upstream's platform support surface rather than extending it.
