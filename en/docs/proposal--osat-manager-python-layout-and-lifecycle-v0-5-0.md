---
title: "Proposal: osat-manager-python layout, lifecycle and aliases"
description: "Proposed layout, commands, aliases and status output for osat-manager-python, the successor to osat-fluent-python-tool, with advantages, disadvantages and notes."
date: 2026-09-29
version: "0.5.0"
status: "Draft"
---

# Proposal: osat-manager-python layout, lifecycle and aliases

Version: 0.5.0
Status: Draft

## Summary

This proposal turns osat-fluent-python-tool, an installer for self-contained CPython runtimes, into osat-manager-python, a full manager in the OSAT Fluent collection. It adopts the collection's lifecycle of install, switch, status and remove, keeps several Python versions installed side by side, and introduces aliases: the commands, such as `python` and `python3.12`, through which users reach them. Every alias can be renamed, and the same lifecycle and alias rules apply to every OSAT manager. The manager itself, `manage-python`, installs alongside the runtimes it manages, so it is available from any directory once installed.

## Design principle

The architecture is built for the scenarios people use every day: install a version, switch between versions, run Python, create venvs. Edge cases and their workarounds are documented as notes, where they help the people who meet them, but they do not shape the design.

## Context

Testing osat-fluent-python-tool 0.2.0 on Windows 11 confirmed that the verified install works and showed what a manager needs to add: a way to keep and switch between versions, a command that follows the version in use, protection for the installed runtimes, and a way to resolve name collisions with other tools such as uv <a id="cite-astral-uv-1"></a>([Astral, n.d.-a](#ref-astral-uv)).

The collection has settled a manager lifecycle in osat-fluent-restic-tool and osat-fluent-sat-tool: versions side by side, a wrapper that reads a version pointer, a permanent verified archive, and `--install`, `--switch`, `--status` and `--remove` <a id="cite-steel-restic-1"></a>([Steel, 2026b](#ref-steel-restic)). This proposal applies that lifecycle to Python.

## Proposed changes

### Naming and management identifier

The repository osat-fluent-python-tool is renamed osat-manager-python, keeping its history, and its first release under the new name is 0.3.0. GitHub redirects the old repository URL.

Each manager carries two names with different jobs:

- The **management identifier**, `python-manager`, names the namespace that owns files: `~/.local/share/python-manager/`, `~/.config/python-manager/` and the `PYTHON_MANAGER_*` variables. `-manager` is the collection's target identifier. The existing managers keep `-tool` until they move to it, and Python is the first manager built to the target.
- The **command**, `manage-python`, names the program users run. The script is `manage-python.py`, and the collection follows the same pattern: `manage-restic`, `manage-rclone`, `manage-sat`.

The two never compete. Users never type the identifier, and the command never names a directory by itself. `install.sh` and `install.ps1` remain as bootstrap entry points for machines without a suitable Python.

### Filesystem layout

Linux and macOS use the same XDG locations, as the collection specification defines, and respect `XDG_DATA_HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME` when they are set:

```text
~/.local/bin/
    manage-python                           alias for the manager itself
    python                                  alias for the default version
    python3.12                              alias per minor version
    python3.13

~/.local/share/python-manager/
    manage-python/0.3.0/manage-python.py    the manager, plus PROVENANCE
    manage-python/0.3.0/locale/             its translations
    3.12.14/python/bin/python3.12           runtime, plus PROVENANCE
    3.12.13/python/bin/python3.12           versions side by side
    3.13.15/python/bin/python3.13
    archive/3.12.14+20260924/               verified release tarball

~/.config/python-manager/
    python-manager.env                      manager pointer
    env                                     operator environment, never touched by the manager

~/.local/state/python-manager/              state and logs
```

Windows:

```text
%LOCALAPPDATA%\Programs\
    manage-python.cmd   manage-python.ps1
    python.cmd          python.ps1
    python3.12.cmd      python3.12.ps1
    python3.13.cmd      python3.13.ps1

%LOCALAPPDATA%\python-manager\
    manage-python\0.3.0\manage-python.py    the manager, plus PROVENANCE
    manage-python\0.3.0\locale\             its translations
    3.12.14\python\python.exe               runtime, plus PROVENANCE
    3.12.13\python\python.exe
    3.13.15\python\python.exe
    archive\3.12.14+20260924\               verified release tarball
    python-manager.env.cmd                  manager pointer
    python-manager.env.ps1
    logs\

%APPDATA%\python-manager\
    env.cmd          env.ps1                operator environment
```

Install directories are named by micro version, for example `3.12.14`. The python-build-standalone build tag, for example `20260924`, is recorded in `PROVENANCE` and used in the archive path <a id="cite-astral-pbs-1"></a>([Astral, n.d.-b](#ref-astral-pbs)).

#### Versions side by side

```text
~/.local/share/python-manager/
    3.12.14/python/bin/python3.12           runtime, plus PROVENANCE
    3.12.13/python/bin/python3.12           versions side by side
```

Each version gets its own directory, named by its full version, and `--switch` chooses which one the aliases run. Nothing is replaced, so moving between versions is immediate and venvs keep the version that created them.

The interpreter inside is named `python3.12`, not `python3.12.14`, because the directory holds the runtime exactly as python-build-standalone ships it. CPython names its executable and library paths by minor version only (`bin/python3.12`, `lib/python3.12/`), and tools such as `venv` and pip expect those names. The full version lives in the directory name and in `PROVENANCE` instead.

### The manager itself

On first run, from a downloaded release or through `install.sh` or `install.ps1`, the manager installs a copy of itself under `python-manager/manage-python/<version>/` and writes a `manage-python` alias. From then on every command runs from any directory, and the downloaded release can be deleted. New manager versions install side by side, like runtimes, which leaves room for the collection's self-update approach.

After installation the `manage-python` alias runs the manager on the default Python runtime, on every platform. This matters most on Windows, where no system Python remains once the bootstrap copy is gone. Because `--remove` refuses to remove the default version, the manager can never remove the Python it runs on.

On Linux and macOS, the first install can use the system `python3`, version 3.8 or later, with the standard library only. On Windows, and on any system without a suitable Python, the bootstrap scripts provide a temporary interpreter for the first install and then delete it.

### Aliases

An alias is a command the manager writes so users can reach an installed version. osat-manager-python writes two kinds:

- `python`, which runs the default version.
- One alias per minor version, such as `python3.12` and `python3.13`, each running the default version of that minor line.

The generic `python` gives developers one command for everyday work that keeps working as versions change. The versioned aliases give scripts and other managers a name that stays on one minor version. The manager's own `manage-python` command is an alias too, and follows the same rules.

Any alias can be renamed:

```bash
manage-python --alias python3.12=py312
```

Renaming changes only the command's name. The alias still follows the same version, and the rename is kept across switches and installs. Every OSAT manager has aliases (restic-manager's is `restic`), and `--alias` works the same way in each.

The manager never silently overwrites an alias file it did not write. If a name is already taken, it stops and suggests `--alias`. Its own files are recognised by their provenance header, which names `manage-python.py`.

osat-manager-python does not write `python3` or `pip`. On Debian-family systems `python3` belongs to the system interpreter, and in a venv `pip` comes from the venv.

#### Change from 0.2.0

0.2.0 deliberately wrote only versioned wrappers such as `python3.12`, to avoid quietly shadowing a system Python. 0.3.0 adds `python` as a deliberate, visible choice rather than a quiet one: it is listed in `--status`, it can be renamed, and the manager never overwrites a `python` it did not write. On distributions that ship a `python` command, such as Debian-family systems with `python-is-python3` installed, the manager's `python` comes first on PATH for the user who installed it, while system tools that call `/usr/bin/python3` by absolute path are unaffected.

### Lifecycle commands

```bash
manage-python --install                      # latest version of the default minor line
manage-python --install 3.13                 # latest version of a minor line
manage-python --install 3.12.14              # a specific version
manage-python --install 3.12.14+20260924     # a specific build, no API call
manage-python --switch 3.12.13               # make 3.12.13 the version behind python and python3.12
manage-python --status                       # aliases, defaults, installed and archived versions
manage-python --remove 3.12.13               # remove a version that no alias uses, archive kept
manage-python --alias python3.12=py312       # rename an alias
manage-python --lang fr --status             # run a command in another language
manage-python --version                      # this manager's version
```

The first install runs the downloaded script directly, for example `python3 manage-python.py --install`, or through `install.sh` or `install.ps1`.

`--switch` takes a full version and makes it current. It works the same way in every OSAT manager: `--switch 3.12.13` here, `--switch 0.19.1` for restic. Other installed versions stay installed and can be switched to at any time. In osat-manager-python, switching to 3.12.13 points both `python` and `python3.12` at it and leaves other minor lines as they are.

`--install` installs a version and switches to it, as it does in every manager. A pinned build skips the GitHub Releases API, as pinned restic versions do.

### Status output

```text
3.12
  aliases     python3.12  python
    default     3.12.14
    installed   3.12.13
    archived    3.12.12+20260715

3.13
  aliases     python3.13
    default     3.13.15
```

Each minor line lists its aliases, then the versions behind them. `python` appears under the minor line it currently runs, so a switch visibly moves it. "default" is the version the aliases run, "installed" is on disk and available through `--switch`, and "archived" is removed but restorable offline. A renamed alias appears under its new name.

### Pointer file

The pointer records which version each alias runs, and the name each alias is written under:

```sh
PYTHON_MANAGER_DEFAULT="3.12.14"
PYTHON_MANAGER_3_12="3.12.14"
PYTHON_MANAGER_3_13="3.13.15"

PYTHON_MANAGER_ALIAS_DEFAULT="python"
PYTHON_MANAGER_ALIAS_3_12="py312"
PYTHON_MANAGER_ALIAS_3_13="python3.13"
```

Each alias reads a fixed version key: `python` reads `PYTHON_MANAGER_DEFAULT` and each versioned alias reads the key for its minor line. The alias lines record the names, so `--install` and `--switch` rewrite each alias under the name the user chose, and `--alias` changes only the alias line and the file name. On Windows the pointer lives in `%LOCALAPPDATA%\python-manager\`, beside the versions it names.

### Platforms

#### Supported platforms

osat-manager-python supports the platforms python-build-standalone publishes runtimes for. As of release 20260929 these are:

| Operating system | Builds |
| --- | --- |
| Linux, glibc | x86-64 (with `x86_64_v2`, `v3` and `v4` variants), ARM64, 32-bit ARM, POWER (`ppc64le`), RISC-V (`riscv64`), IBM Z (`s390x`) |
| Linux, musl | x86-64 (with variants), ARM64 |
| macOS | Apple Silicon, Intel |
| Windows | x86-64, 32-bit x86, ARM64 |

There are no FreeBSD, OpenBSD or other BSD builds, so the manager cannot install Python on those systems.

macOS is not an exception to this. Its Darwin foundation has BSD heritage, and the BSD part of its kernel derives mainly from FreeBSD <a id="cite-apple-bsd-1"></a>([Apple, n.d.](#ref-apple-bsd)), but that code runs inside XNU alongside Mach, and macOS uses its own executable format and system libraries. Programs built for FreeBSD do not run on macOS, and programs built for macOS do not run on FreeBSD, which is why python-build-standalone publishes macOS builds separately and why they do not help on the BSDs.

#### Runtime selection

python-build-standalone names each build by an LLVM target triple <a id="cite-szorc-pbs-1"></a>([Szorc, n.d.](#ref-szorc-pbs)). The manager selects the triple from the operating system and CPU architecture, and on Linux from the C library. The common cases are:

| Platform | Triple |
| --- | --- |
| Linux, x86-64, glibc | `x86_64-unknown-linux-gnu` |
| Linux, ARM64, glibc | `aarch64-unknown-linux-gnu` |
| Linux, x86-64, musl | `x86_64-unknown-linux-musl` |
| Linux, ARM64, musl | `aarch64-unknown-linux-musl` |
| macOS, Apple Silicon | `aarch64-apple-darwin` |
| macOS, Intel | `x86_64-apple-darwin` |
| Windows, x86-64 | `x86_64-pc-windows-msvc` |
| Windows, ARM64 | `aarch64-pc-windows-msvc` |

The manager uses the baseline x86-64 builds rather than the `x86_64_v2`, `v3` and `v4` variants, so a runtime installed on one machine also runs on older ones, and the `install_only_stripped` flavour, as 0.2.0 does. The selected triple is recorded in `PROVENANCE`.

#### Alias wrappers

On Linux and macOS each alias is a POSIX `sh` script that reads the operator environment and the pointer, then replaces itself with the runtime:

```sh
#!/bin/sh
# Rendered by manage-python.py. Do not edit; re-run the manager instead.
config="${XDG_CONFIG_HOME:-$HOME/.config}/python-manager"
[ -r "$config/env" ] && . "$config/env"
. "$config/python-manager.env"
exec "${XDG_DATA_HOME:-$HOME/.local/share}/python-manager/$PYTHON_MANAGER_3_12/python/bin/python3" "$@"
```

On Windows each alias is a `.cmd` and `.ps1` pair doing the same:

```bat
@echo off
rem Rendered by manage-python.py. Do not edit; re-run the manager instead.
setlocal
if exist "%APPDATA%\python-manager\env.cmd" call "%APPDATA%\python-manager\env.cmd"
call "%LOCALAPPDATA%\python-manager\python-manager.env.cmd"
"%LOCALAPPDATA%\python-manager\%PYTHON_MANAGER_3_12%\python\python.exe" %*
```

`setlocal` keeps the pointer's variables out of the calling shell.

#### PATH

Linux distributions add `~/.local/bin` to PATH automatically. macOS does not, so the installer prints the line to add to `~/.zshrc`, as the collection specification describes. On Windows the installer prepends `%LOCALAPPDATA%\Programs` to the user PATH.

### Protecting the installed runtimes

After extracting a runtime, the manager writes an `EXTERNALLY-MANAGED` file into that runtime's standard library directory. pip then refuses to install into the runtime itself and shows the manager's message, which points users to `python3.12 -m venv` <a id="cite-pypa-em-1"></a>([Python Packaging Authority, n.d.](#ref-pypa-em)). Venvs are unaffected. Anaconda's protected base installer takes the same approach for the same reason: installing into the base environment is the most common way users break their installation <a id="cite-anaconda-pbe-1"></a>([Anaconda, n.d.](#ref-anaconda-pbe)).

### Archive and provenance

The archive holds each verified release tarball. It can be checked against its recorded SHA-256 at any time, and restoring it means verify, extract and health-check. A runtime is archived only after its `python` starts and reports the expected version.

Extraction uses the `data` filter of `tarfile` where the running Python supports it. This rejects unsafe paths in an archive and removes the deprecation warning 0.2.0 prints.

### Translations

The manager's interactive content is translated with gettext, which is part of the Python standard library, so translation adds no dependency. Its `.po` format is the one translators and their tools already use, and it handles plural forms.

In the repository, a template `locale/manage-python.pot` is extracted from the source, and each language has `locale/<lang>/LC_MESSAGES/manage-python.po`, for example `fr`. At release time these are compiled to `.mo` files, which ship with the manager and install at `manage-python/<version>/locale/<lang>/LC_MESSAGES/manage-python.mo`. Translations travel with the manager version they belong to, so a manager version is never paired with another version's messages, and users need no translation tools.

The language is chosen in this order: the `--lang` option, then `PYTHON_MANAGER_LANG` in the operator environment, then the system locale, then English.

Messages, prompts and status labels such as "default", "installed" and "archived" are translated. Command names, options, pointer keys and file names never are, and any future machine-readable status output stays untranslated so scripts can parse it. Messages shared by every manager, such as switch and remove confirmations, can later move to the collection's shared module with a catalog of their own.

## Advantages and disadvantages

| Decision | Advantages | Disadvantages |
| --- | --- | --- |
| `-manager` identifier | Names what the software does; Python sets the pattern for the collection | The other managers keep `-tool` until migrated |
| Versions side by side | Developers keep every version they install and move between them freely | Disk use grows until versions are removed |
| One `--switch` rule for every manager | Nothing Python-specific to learn; the same command works everywhere | None identified |
| Generic `python` alias | One everyday command that follows the version in use | Scripts that need a fixed minor version should use a versioned alias |
| Renamable aliases | Any name collision is resolved with one command, on any manager | Users renaming an alias need to remember the new name |
| No `python3` or `pip` aliases | Leaves the system interpreter and venv tooling as users expect | Users coming from other tools may look for them |
| `EXTERNALLY-MANAGED` marker | Keeps installed runtimes clean; follows established practice | A deliberate global install needs `--break-system-packages` |
| Tarball archive with build tag | Exact provenance and offline restore | Archive grows with each build installed |
| `manage-<name>` commands | Reads as what you run; one pattern across the collection | Each manager has two names to learn, its command and its identifier |
| Manager installs itself | Works from any directory; the download can be deleted; manager versions sit side by side | The manager depends on the default runtime it manages |
| gettext translations | Standard library only; familiar to translators; versioned with the manager | A compile step at release time |

## Testing before release

The manager's logic is tested with the standard library's `unittest`: pointer and alias record parsing, platform triple selection, version resolution and status output. A scripted end-to-end run installs, switches, renames, removes and restores real python-build-standalone runtimes, and is run on each platform listed below. Neither adds a dependency.

Each release is tested on every platform it claims to support. A platform without hardware available is listed as untested in the release notes rather than claimed.

| Platform | Machine | Status |
| --- | --- | --- |
| Linux x86-64 | Linux Mint 22.3 workstation | Tested every release |
| Windows 11 x86-64 | Windows 11 virtual machine | Tested every release |
| macOS Apple Silicon | Apple Silicon Mac | Needs hardware |
| macOS Intel | Intel Mac | Optional, listed as untested without hardware |
| NixOS x86-64 | NixOS machine or virtual machine | Listed as untested until run |
| Linux ARM64, Linux musl, Windows ARM64 | As available | Listed as untested without hardware |

On every platform:

- Install two minor lines and two versions of one of them, then switch between the versions and check `python --version` and the versioned alias.
- Rename an alias, then install and switch again, and check that the new name is kept.
- Check `--status` against what is on disk.
- Remove a version, then restore it from the archive with the network disconnected.
- Confirm that pip refuses to install into a runtime, and that a venv created from an alias installs normally.

On Windows, in a default Windows 11 session:

- Whether PowerShell runs `python3.12.ps1` or `python3.12.cmd` when both exist, and what happens when the default execution policy blocks scripts. `Get-Command python3.12` in a fresh session shows which one it picks.
- Whether Ctrl+C in the Python REPL leaves a "Terminate batch job (Y/N)?" prompt behind when Python runs through a `.cmd` wrapper.
- Whether a batch file that runs `python3.12` without `call` continues after Python exits.

On macOS, whether Gatekeeper allows the runtimes to run without prompting.

## Notes

These notes cover situations some users will meet. They are documentation, not design constraints.

### Coexisting with uv

uv writes versioned aliases such as `python3.12` into `~/.local/bin` and does not overwrite files it did not write <a id="cite-astral-uv-2"></a>([Astral, n.d.-a](#ref-astral-uv)). If both tools want the same name, rename one side: `--alias` on the OSAT side, or `uv python install --no-bin` on the uv side.

### The Microsoft Store alias

Windows includes a `python.exe` alias in `%LOCALAPPDATA%\Microsoft\WindowsApps` that opens the Microsoft Store. The installer prepends `%LOCALAPPDATA%\Programs` to the user PATH so that the manager's `python` comes first. Users can also turn the Store alias off under Settings > Apps > Advanced app settings > App execution aliases.

### Venvs and removed versions

A venv records the runtime that created it and keeps using it after a switch. Removing that runtime stops the venv from working, and reinstalling it from the archive restores it to the same path. Moving venvs between versions, or across a future directory rename, will be addressed on the way to 1.0.0.

### Roaming profiles on Windows

On machines with roaming profiles, `%APPDATA%` follows the user between machines while `%LOCALAPPDATA%` does not. Keeping the pointer in `%LOCALAPPDATA%` means it always describes the machine it is on.

### A fresh Linux account

Debian-family distributions add `~/.local/bin` to PATH at login only if the directory already exists. On an account where the manager creates it for the first time, the aliases work after the next login, or immediately after running `. ~/.profile`.

### The system python3

Linux distributions and macOS keep their own `python3`, used by system tools and by scripts that start with `#!/usr/bin/env python3`. The manager's `python` alias sits beside it and does not replace it.

### Rosetta on Apple Silicon

A Python running under Rosetta reports an Intel architecture, which would select the Intel runtime on an Apple Silicon Mac. The manager checks whether it is running translated and selects the Apple Silicon build.

### musl-based Linux

Distributions such as Alpine use musl rather than glibc. The manager detects this and selects the musl build. python-build-standalone's musl builds are statically linked, and as a side effect they cannot load compiled extension modules <a id="cite-szorc-pbs-2"></a>([Szorc, n.d.](#ref-szorc-pbs)). Pure-Python packages work, but packages that ship compiled code may not.

### NixOS

NixOS does not keep a dynamic loader at the standard path, such as `/lib64/ld-linux-x86-64.so.2`, because its loader lives in the Nix store. The glibc builds expect the standard path, so on a default NixOS system running a runtime fails with a "No such file or directory" error, even though the file exists. Enabling nix-ld in the system configuration places a shim loader at the standard path and lets such binaries run unmodified <a id="cite-nixld-1"></a>([nix-community, n.d.](#ref-nixld)):

```nix
programs.nix-ld.enable = true;
```

The musl builds do not need the loader, but their limit on compiled extension modules makes nix-ld the recommended route. The wrappers need only `/bin/sh`, which NixOS provides.

## Collection-wide implications

Adopting this proposal implies the following changes to the OSAT user-space installation specification and the other managers <a id="cite-steel-spec-1"></a>([Steel, 2026a](#ref-steel-spec)):

- Record `-manager` as the target management identifier, and `manage-<name>` as the command pattern.
- Define that each manager installs itself under `<identifier>/manage-<name>/<version>/` and is reached through its own alias.
- Define gettext as the translation mechanism, with catalogs versioned alongside each manager.
- Define aliases, `--alias`, the alias record in the pointer file, and the rule that a manager never silently overwrites a file it did not write.
- Define `--switch` as taking a full version in every manager.
- Use "default", "installed" and "archived" in status output, replacing "active".
- Place the version pointer in `%LOCALAPPDATA%\<identifier>\` on Windows.

## References

<a id="ref-anaconda-pbe"></a>Anaconda. (n.d.). *Protected base installers*. Anaconda documentation. https://www.anaconda.com/docs/getting-started/protected-base-beta [↩](#cite-anaconda-pbe-1)

<a id="ref-apple-bsd"></a>Apple. (n.d.). *BSD overview*. Kernel programming guide. Apple Developer Documentation Archive. https://developer.apple.com/library/content/documentation/Darwin/Conceptual/KernelProgramming/BSD/BSD.html [↩](#cite-apple-bsd-1)

<a id="ref-astral-uv"></a>Astral. (n.d.-a). *Python versions*. uv documentation. https://docs.astral.sh/uv/concepts/python-versions/ [↩](#cite-astral-uv-1)

<a id="ref-astral-pbs"></a>Astral. (n.d.-b). *python-build-standalone* [Computer software]. GitHub. https://github.com/astral-sh/python-build-standalone [↩](#cite-astral-pbs-1)

<a id="ref-nixld"></a>nix-community. (n.d.). *nix-ld* [Computer software]. GitHub. https://github.com/nix-community/nix-ld [↩](#cite-nixld-1)

<a id="ref-pypa-em"></a>Python Packaging Authority. (n.d.). *Externally managed environments*. Python Packaging User Guide. https://packaging.python.org/en/latest/specifications/externally-managed-environments/ [↩](#cite-pypa-em-1)

<a id="ref-steel-spec"></a>Steel, C. (2026a). *OSAT user-space installation specification* (Version 0.2.0). GitHub. https://github.com/steelcj/osat-fluent [↩](#cite-steel-spec-1)

<a id="ref-steel-restic"></a>Steel, C. (2026b). *osat-fluent-restic-tool* [Computer software]. GitHub. https://github.com/steelcj/osat-fluent-restic-tool [↩](#cite-steel-restic-1)

<a id="ref-szorc-pbs"></a>Szorc, G. (n.d.). *Running distributions*. python-build-standalone documentation. https://gregoryszorc.com/docs/python-build-standalone/main/running.html [↩](#cite-szorc-pbs-1)

## License

This document, *Proposal: osat-manager-python layout, lifecycle and aliases*, by **Christopher Steel**, with AI assistance from **Claude (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Changelog

| Version | Status | Notes |
| --- | --- | --- |
| 0.5.0 | Draft | Decisions for the reference implementation: repository renamed to osat-manager-python with 0.3.0 as its first release; management identifier and command separated, with `manage-python` and the `manage-<name>` pattern; the manager installs itself, is reached through its own alias and runs on the default runtime; Python 3.8 floor for first installs on Linux and macOS; gettext translations and their locations; `unittest` and end-to-end testing; change from 0.2.0's versioned-only wrappers explained |
| 0.4.0 | Draft | Versions side by side note, including why the interpreter keeps its minor-version name. Supported platforms defined as those python-build-standalone publishes, checked against release 20260929, with the absence of BSD builds and the difference between macOS and the BSDs explained. Windows ARM64 and Linux ARM64 musl added to runtime selection. NixOS note and test matrix line. musl note expanded with the static-linking limit. References added for Apple, nix-ld and the python-build-standalone documentation |
| 0.3.0 | Draft | Platforms section: runtime selection by platform triple, alias wrappers for POSIX and Windows, PATH per platform. Alias names recorded in the pointer so renames survive installs and switches. XDG overrides respected on Linux and macOS. Testing covers every platform, with untested platforms declared in release notes. Notes for fresh Linux accounts, the system python3, Rosetta and musl |
| 0.2.0 | Draft | Design principle added: architecture for everyday scenarios, edge cases as notes. `--switch` takes a full version in every manager. Aliases introduced, with `--alias` for renaming, replacing ownership reporting. Status output uses an aliases row. Pointer keyed by minor line so renames never change it. uv, Store alias, venv and roaming-profile material moved to notes; venv migration deferred to the road to 1.0.0. References checked |
| 0.1.0 | Draft | Initial proposal from Windows testing of osat-fluent-python-tool 0.2.0 |
