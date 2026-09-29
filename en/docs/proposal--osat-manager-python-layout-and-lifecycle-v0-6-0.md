---
dc:title: "Proposal: osat-manager-python Layout, Lifecycle and Aliases"
dcterms:version: "0.6.0"
dc:creator: "Christopher Steel"
dc:contributor: "Claude Opus 5.5 (Anthropic)"
dc:description: "Proposed layout, commands, aliases, status output, translations and testing for osat-manager-python, the successor to osat-fluent-python-tool, with advantages, disadvantages and notes."
dcterms:created: "2026-09-28"
dcterms:modified: "2026-09-29"
dc:format: "text/markdown"
dc:language: "en"
sat:language_bcp47: "en"
dc:identifier: "proposal--osat-manager-python-layout-and-lifecycle"
dcterms:rightsHolder: "Christopher Steel"
dc:rights: >
  Copyright 2026 Christopher Steel.
  SPDX-License-Identifier: GPL-3.0-or-later
sat:uuid: ""
sat:repository: "osat-manager-python"
sat:path: "en/docs/"
sat:version_at_creation: "0.4.0"
sat:migration_status: pre-sat
sat:changelog:
  - version: "0.6.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Restructured to the technical documentation guide: the old
      implementation described, proposed changes presented as the new
      implementation, alternatives considered recorded for each decision,
      and a new section defining the contracts between components, the
      pointer file, alias wrappers, PROVENANCE, runtimes used by other
      managers, and operator output and logging. Alias wrappers aligned
      with restic-tool's template header and sourcing order.
  - version: "0.5.1"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Conformance pass against the repository's markdown defaults and the
      versioned-documents style guide: Dublin Core frontmatter, Style Guide
      line naming the technical guide, Abstract, Sources and
      Acknowledgements, Resources, Citation Anchor Pairs in the house
      format, canonical closing sequence, and the code documentation
      license template. Content unchanged.
  - version: "0.5.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Decisions for the reference implementation: repository rename,
      identifier and command separated, the manager installs itself,
      Python 3.8 floor for first installs, gettext translations, testing.
  - version: "0.4.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: "Supported platforms, NixOS, musl and versions side by side notes."
  - version: "0.3.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: "Platforms section, alias record, testing on every platform."
  - version: "0.2.0"
    date: "2026-09-28"
    author: "Christopher Steel"
    notes: "Design principle, single switch rule, aliases, edge cases as notes."
  - version: "0.1.0"
    date: "2026-09-28"
    author: "Christopher Steel"
    notes: "Initial proposal from Windows testing of osat-fluent-python-tool 0.2.0."
---

# Proposal: osat-manager-python Layout, Lifecycle and Aliases

Version: 0.6.0
Status: Draft
Style Guide: style-guide--technical-documentation-for-technologists

## Abstract

This proposal turns osat-fluent-python-tool, an installer for self-contained CPython runtimes, into osat-manager-python, a full manager in the OSAT Fluent collection. It adopts the collection's lifecycle of install, switch, status and remove, keeps several Python versions installed side by side, and introduces aliases: the commands, such as `python` and `python3.12`, through which users reach them. Every alias can be renamed, and the same lifecycle and alias rules apply to every OSAT manager. The manager itself, `manage-python`, installs alongside the runtimes it manages, so it is available from any directory once installed. The proposal describes the 0.2.0 implementation it replaces, records the alternatives considered for each decision, and defines the contracts other components rely on: the pointer file, the alias wrappers, `PROVENANCE`, and operator output.

## Sources and Acknowledgements

This proposal derives from the OSAT user-space installation specification <a name="apa-osat-spec-citation"></a>([Steel, 2026a](#apa-osat-spec-reference)) and from the manager lifecycle established in osat-fluent-restic-tool <a name="apa-restic-tool-citation"></a>([Steel, 2026b](#apa-restic-tool-reference)). Runtimes come from the python-build-standalone project <a name="apa-pbs-repo-citation"></a>([Astral, n.d.-b](#apa-pbs-repo-reference)), whose documentation defines the platform triples used here <a name="apa-pbs-docs-citation"></a>([Szorc, n.d.](#apa-pbs-docs-reference)). Protection of installed runtimes follows the Python packaging specification for externally managed environments <a name="apa-pypa-em-citation"></a>([Python Packaging Authority, n.d.](#apa-pypa-em-reference)). The design was developed from testing osat-fluent-python-tool 0.2.0 on Windows 11 and Linux Mint 22.3, with AI assistance from Claude Opus 5.5 (Anthropic).

## Design principle

The architecture is built for the scenarios people use every day: install a version, switch between versions, run Python, create venvs. Edge cases and their workarounds are documented as notes, where they help the people who meet them, but they do not shape the design.

## Context

Testing osat-fluent-python-tool 0.2.0 on Windows 11 confirmed that the verified install works and showed what a manager needs to add: a way to keep and switch between versions, a command that follows the version in use, protection for the installed runtimes, and a way to resolve name collisions with other tools such as uv <a name="apa-uv-python-versions-citation"></a>([Astral, n.d.-a](#apa-uv-python-versions-reference)).

The collection has settled a manager lifecycle in osat-fluent-restic-tool and osat-fluent-sat-tool: versions side by side, a wrapper that reads a version pointer, a permanent verified archive, and `--install`, `--switch`, `--status` and `--remove` <a name="apa-restic-tool-citation-2"></a>([Steel, 2026b](#apa-restic-tool-reference)). This proposal applies that lifecycle to Python.

## The old implementation

osat-fluent-python-tool 0.2.0 is an installer. Its script, `install-python.py`, requires Python 3.8 or later and uses only the standard library. It looks up the latest python-build-standalone release through the GitHub Releases API, downloads the `install_only_stripped` build for the platform, verifies it against the release's `SHA256SUMS`, extracts it to `~/.local/share/python-tool/<version>/` (`%LOCALAPPDATA%\python-tool\<version>\` on Windows), and writes one wrapper per minor version, such as `python3.12`, to `~/.local/bin/` (`%LOCALAPPDATA%\Programs\` on Windows). A `--track` option selects the minor version and `--force` reinstalls. `install.sh` and `install.ps1` bootstrap machines without a suitable Python by fetching a pinned, disposable interpreter (python-build-standalone release 20250828, CPython 3.11.13), running the installer with it, and deleting it.

0.2.0 has no way to list, switch between or remove versions; removal is manual. It deliberately writes only versioned wrappers and never a bare `python` or `python3`. It has been tested end to end on Linux, and on Windows 11 during the testing that led to this proposal.

## The new implementation

We keep what 0.2.0 does well, verified downloads from a single governed source, versioned directories and user-space installation with no elevation, and add what a manager needs. Each decision below records what we chose, why, and the alternatives we considered.

### Naming and management identifier

The repository osat-fluent-python-tool is renamed osat-manager-python, keeping its history, and its first release under the new name is 0.3.0. GitHub redirects the old repository URL.

Each manager carries two names with different jobs:

- The **management identifier**, `python-manager`, names the namespace that owns files: `~/.local/share/python-manager/`, `~/.config/python-manager/` and the `PYTHON_MANAGER_*` variables. `-manager` is the collection's target identifier. The existing managers keep `-tool` until they move to it, and Python is the first manager built to the target.
- The **command**, `manage-python`, names the program users run. The script is `manage-python.py`, and the collection follows the same pattern: `manage-restic`, `manage-rclone`, `manage-sat`.

The two never compete. Users never type the identifier, and the command never names a directory by itself. `install.sh` and `install.ps1` remain as bootstrap entry points for machines without a suitable Python.

#### Alternatives considered

We considered keeping the `-tool` identifier. It describes an installer rather than something that manages versions over time, and the collection is moving to `-manager`, so Python adopts the target first. We considered naming the command after the identifier, `python-manager`, but a noun reads as a thing rather than an action, and `manage-python` reads as what the user does. We considered `install-python.py`, the 0.2.0 name, but it reads oddly once the script also switches, removes and renames.

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

Install directories are named by micro version, for example `3.12.14`. The python-build-standalone build tag, for example `20260924`, is recorded in `PROVENANCE` and used in the archive path <a name="apa-pbs-repo-citation-2"></a>([Astral, n.d.-b](#apa-pbs-repo-reference)).

#### Versions side by side

```text
~/.local/share/python-manager/
    3.12.14/python/bin/python3.12           runtime, plus PROVENANCE
    3.12.13/python/bin/python3.12           versions side by side
```

Each version gets its own directory, named by its full version, and `--switch` chooses which one the aliases run. Nothing is replaced, so moving between versions is immediate and venvs keep the version that created them.

The interpreter inside is named `python3.12`, not `python3.12.14`, because the directory holds the runtime exactly as python-build-standalone ships it. CPython names its executable and library paths by minor version only (`bin/python3.12`, `lib/python3.12/`), and tools such as `venv` and pip expect those names. The full version lives in the directory name and in `PROVENANCE` instead.

#### Alternatives considered

We considered a `~/.local/bin/osat/` subdirectory for OSAT aliases. Distributions add `~/.local/bin` to PATH but not its subdirectories, and the collection specification already rejects subdirectories there, so users would have to add it by hand. We considered a single OSAT root, `~/.local/share/osat/`, holding every manager and its own `bin/` directory. It gives clean ownership and a single removal point, but it departs from the XDG convention of one directory per application and would require migrating every manager at once; we keep it in mind for the general specification rather than adopting it here. On Windows we considered a subfolder per manager under `%LOCALAPPDATA%\Programs\`, which would add a PATH entry per manager, so we keep the specification's single shared directory.

### The manager itself

On first run, from a downloaded release or through `install.sh` or `install.ps1`, the manager installs a copy of itself under `python-manager/manage-python/<version>/` and writes a `manage-python` alias. From then on every command runs from any directory, and the downloaded release can be deleted. New manager versions install side by side, like runtimes, which leaves room for the collection's self-update approach.

After installation the `manage-python` alias runs the manager on the default Python runtime, on every platform. This matters most on Windows, where no system Python remains once the bootstrap copy is gone. Because `--remove` refuses to remove the default version, the manager can never remove the Python it runs on.

On Linux and macOS, the first install can use the system `python3`, version 3.8 or later, with the standard library only. On Windows, and on any system without a suitable Python, the bootstrap scripts provide a temporary interpreter for the first install and then delete it.

#### Alternatives considered

We considered continuing to run the manager from the downloaded release, as 0.2.0 does. That keeps it an installer: switching or checking status would require keeping the download and running it from its directory. We considered a top-level `manage-python/` directory in `share/`, which would give each manager two directories there; a subdirectory keeps everything a manager owns under its identifier. We considered running the installed manager on the system `python3`, but Windows has none once the bootstrap interpreter is removed, and one rule for every platform is simpler.

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

#### Alternatives considered

We considered a `python3` alias. Scripts that start with `#!/usr/bin/env python3` expect the system interpreter and its distribution packages, and shadowing it would break them in confusing ways. We considered `pip` and `pip3` aliases; with several minor lines installed their meaning is ambiguous, and they would target the installed runtimes, which refuse installs under this proposal. We considered keeping 0.2.0's versioned-only aliases, which leaves developers without a command that follows their switches. For name collisions we considered reporting which tool owns each name in `--status`; a refusal at write time plus `--alias` resolves the same situations with far less machinery.

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

#### Alternatives considered

We considered letting `--switch` accept a minor version to move `python` between minor lines, alongside a separate `--default` option. That gives users two rules to learn and gives Python behaviour no other manager shares; one rule, a full version, works everywhere. We considered a `--patch` verb, which reads as applying a patch and would exist only in Python. We considered switching by symbolic links or Windows directory junctions instead of a pointer. The collection specification rejects symbolic links because they cannot carry environment settings and do not behave uniformly on Windows, and a junction that venvs resolved through would move existing venvs to a new version without warning; we prefer venvs to stay on the version that created them.

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

#### Alternatives considered

We considered several words for the version an alias runs. "active" collides with venv activation, which Python developers do constantly. "current" served for a time but left the version behind `python` needing a second word. "enabled" implies that other versions are disabled, although they run for any venv built on them. "local" already means a per-directory version in pyenv, and we reserve it for a possible `.python-version` feature. "available" means "can be downloaded" in most Python tooling. "default" describes exactly what an alias runs when nothing else is specified.

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

#### Alternatives considered

We considered `%APPDATA%`, where the collection specification and restic-tool currently place the manager's settings on Windows. `%APPDATA%` follows the user between machines on roaming profiles while `%LOCALAPPDATA%` does not, so a pointer there can name versions that are not installed on the machine the user signs in to. We considered storing alias names in a separate file; keeping them in the pointer means one file describes everything the aliases need.

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

macOS is not an exception to this. Its Darwin foundation has BSD heritage, and the BSD part of its kernel derives mainly from FreeBSD <a name="apa-apple-bsd-citation"></a>([Apple, n.d.](#apa-apple-bsd-reference)), but that code runs inside XNU alongside Mach, and macOS uses its own executable format and system libraries. Programs built for FreeBSD do not run on macOS, and programs built for macOS do not run on FreeBSD, which is why python-build-standalone publishes macOS builds separately and why they do not help on the BSDs.

#### Runtime selection

python-build-standalone names each build by an LLVM target triple <a name="apa-pbs-docs-citation-2"></a>([Szorc, n.d.](#apa-pbs-docs-reference)). The manager selects the triple from the operating system and CPU architecture, and on Linux from the C library. The common cases are:

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

We considered the `x86_64_v2`, `v3` and `v4` builds, which are faster on newer processors, but a runtime restored from the archive onto an older machine would fail to start. We considered the musl builds as a way around the NixOS loader, but they are statically linked and cannot load compiled extension modules.

#### Alias wrappers

On Linux and macOS each alias is a POSIX `sh` script rendered from a template, with the same header block as restic-tool's wrappers. It reads the pointer, then the operator environment, then replaces itself with the runtime:

```sh
#!/bin/sh
#
# source
#   project: osat-manager-python
#   path: scripts/nix/alias.template
# generated
#   path: ~/.local/bin/python3.12
#   by: manage-python.py
#
# Do not edit generated aliases; regenerated on --install, --switch and --alias.
_cfg="${XDG_CONFIG_HOME:-$HOME/.config}/python-manager"
. "$_cfg/python-manager.env"
[ -f "$_cfg/env" ] && . "$_cfg/env"
exec "${XDG_DATA_HOME:-$HOME/.local/share}/python-manager/$PYTHON_MANAGER_3_12/python/bin/python3" "$@"
```

On Windows each alias is a `.cmd` and `.ps1` pair doing the same:

```bat
@echo off
rem source
rem   project: osat-manager-python
rem   path: scripts/windows/alias.cmd.template
rem generated
rem   path: %LOCALAPPDATA%\Programs\python3.12.cmd
rem   by: manage-python.py
rem
rem Do not edit generated aliases; regenerated on --install, --switch and --alias.
setlocal
call "%LOCALAPPDATA%\python-manager\python-manager.env.cmd"
if exist "%APPDATA%\python-manager\env.cmd" call "%APPDATA%\python-manager\env.cmd"
"%LOCALAPPDATA%\python-manager\%PYTHON_MANAGER_3_12%\python\python.exe" %*
```

`setlocal` keeps the pointer's variables out of the calling shell.

#### PATH

Linux distributions add `~/.local/bin` to PATH automatically. macOS does not, so the installer prints the line to add to `~/.zshrc`, as the collection specification describes. On Windows the installer prepends `%LOCALAPPDATA%\Programs` to the user PATH.

### Protecting the installed runtimes

After extracting a runtime, the manager writes an `EXTERNALLY-MANAGED` file into that runtime's standard library directory. pip then refuses to install into the runtime itself and shows the manager's message, which points users to `python3.12 -m venv` <a name="apa-pypa-em-citation-2"></a>([Python Packaging Authority, n.d.](#apa-pypa-em-reference)). Venvs are unaffected. Anaconda's protected base installer takes the same approach for the same reason: installing into the base environment is the most common way users break their installation <a name="apa-anaconda-pbe-citation"></a>([Anaconda, n.d.](#apa-anaconda-pbe-reference)).

We considered relying on documentation alone. It does not prevent the most common way installed runtimes get broken, and the marker is a standard mechanism that pip already honours.

### Archive and provenance

The archive holds each verified release tarball. It can be checked against its recorded SHA-256 at any time, and restoring it means verify, extract and health-check. A runtime is archived only after its `python` starts and reports the expected version.

Extraction uses the `data` filter of `tarfile` where the running Python supports it. This rejects unsafe paths in an archive and removes the deprecation warning 0.2.0 prints.

We considered archiving the extracted runtime instead of the tarball. An extracted tree is several times larger and cannot be checked against the published checksum, which only covers the tarball.

### Translations

The manager's interactive content is translated with gettext, which is part of the Python standard library, so translation adds no dependency. Its `.po` format is the one translators and their tools already use, and it handles plural forms.

In the repository, a template `locale/manage-python.pot` is extracted from the source, and each language has `locale/<lang>/LC_MESSAGES/manage-python.po`, for example `fr`. At release time these are compiled to `.mo` files, which ship with the manager and install at `manage-python/<version>/locale/<lang>/LC_MESSAGES/manage-python.mo`. Translations travel with the manager version they belong to, so a manager version is never paired with another version's messages, and users need no translation tools.

The language is chosen in this order: the `--lang` option, then `PYTHON_MANAGER_LANG` in the operator environment, then the system locale, then English.

Messages, prompts and status labels such as "default", "installed" and "archived" are translated. Command names, options, pointer keys and file names never are, and any future machine-readable status output stays untranslated so scripts can parse it. Messages shared by every manager, such as switch and remove confirmations, can later move to the collection's shared module with a catalog of their own.

#### Alternatives considered

We considered JSON message catalogs, which need no compile step but have no plural forms and no support in translators' tools. We considered keeping compiled catalogs only in the repository's top-level `locale/`, which would let a manager version run with another version's messages after a switch.

## Contracts between components

Several components meet at boundaries that other code relies on. Each boundary is defined here in full, so that the manager, the alias wrappers and other managers can change independently without breaking one another.

### Pointer file

The manager is the only writer of the pointer file; alias wrappers are its readers. It is written to a temporary file in the same directory and renamed into place, so a reader never sees a partial file. It holds only `PYTHON_MANAGER_*` keys, one per line, in the syntax of the shell that reads it:

| Platform | File | Line syntax |
|---|---|---|
| Linux and macOS | `python-manager.env` | `PYTHON_MANAGER_3_12="3.12.14"` |
| Windows, Command Prompt | `python-manager.env.cmd` | `set "PYTHON_MANAGER_3_12=3.12.14"` |
| Windows, PowerShell | `python-manager.env.ps1` | `$env:PYTHON_MANAGER_3_12 = "3.12.14"` |

Version keys hold full versions, `PYTHON_MANAGER_DEFAULT` names the version behind `python`, and `PYTHON_MANAGER_ALIAS_*` keys hold alias names. The three Windows and POSIX files carry the same keys and values.

### Alias wrappers

Each alias reads the pointer first and the operator environment second, the order restic-tool's wrappers use, so an operator can override a value for their own sessions without editing a manager-owned file. The alias passes every argument through unchanged and returns the runtime's exit status: on Linux and macOS through `exec`, on Windows as the exit code of its last command. The header block's `by:` line is how the manager recognises its own aliases before overwriting one.

### PROVENANCE

Every installed runtime and every installed manager version carries a `PROVENANCE` file: UTF-8, one `key: value` pair per line, owner-only permissions. The first five keys are the ones restic-tool already writes, so one parser reads both; Python adds three:

| Key | Meaning |
|---|---|
| `manager` | The manager and its version, for example `manage-python 0.3.0` |
| `asset` | The release file name |
| `sha256` | Checksum of the release file, verified before extraction |
| `source` | Download URL, or `local archive (<path>)` for an offline restore |
| `installed` | UTC timestamp in ISO 8601 form |
| `version` | Full CPython version, for example `3.12.14` |
| `build` | python-build-standalone release tag, for example `20260924` |
| `triple` | Platform triple, for example `x86_64-unknown-linux-gnu` |

```text
manager: manage-python 0.3.0
asset: cpython-3.12.14+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
sha256: <64 hexadecimal characters>
source: https://github.com/astral-sh/python-build-standalone/releases/download/20260924/cpython-3.12.14+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
installed: 2026-09-29T14:02:11Z
version: 3.12.14
build: 20260924
triple: x86_64-unknown-linux-gnu
```

A manager version's `PROVENANCE` uses the first five keys. `--status` reads these files, and other managers may read them to report which runtime they depend on. Readers ignore keys they do not know, so later versions can add keys without breaking earlier readers.

### Runtimes used by other managers

Another manager, such as sat-manager, reaches a Python runtime through a versioned alias at install time, for example by running `python3.12 -m venv`. The venv it creates records the runtime's directory, so it keeps using that exact version after any switch. `manage-python --remove` warns that venvs built on a version stop working when it is removed, and reinstalling that version from the archive restores the same directory. A consuming manager may read the runtime's `PROVENANCE` to show which Python it depends on.

### Operator output and logging

Output the user asked for, such as `--status` and `--version`, goes to standard output. Progress, warnings and errors go to standard error, prefixed `[manage-python]`, so output can be piped or captured without mixing the two. The manager exits with 0 on success, 1 when an action fails and 2 for incorrect usage. Each lifecycle action, install, switch, remove, alias and restore, appends one line to `manage-python.log` in the state directory, `~/.local/state/python-manager/` or `%LOCALAPPDATA%\python-manager\logs\`, recording the time, the action, the version and the result.

## Implementation

The implementation is `manage-python.py` in this repository, together with its alias templates in `scripts/nix/` and `scripts/windows/`, its message catalogs in `locale/`, and its tests. It is built to the contracts above and released as 0.3.0.

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

uv writes versioned aliases such as `python3.12` into `~/.local/bin` and does not overwrite files it did not write <a name="apa-uv-python-versions-citation-2"></a>([Astral, n.d.-a](#apa-uv-python-versions-reference)). If both tools want the same name, rename one side: `--alias` on the OSAT side, or `uv python install --no-bin` on the uv side.

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

Distributions such as Alpine use musl rather than glibc. The manager detects this and selects the musl build. python-build-standalone's musl builds are statically linked, and as a side effect they cannot load compiled extension modules <a name="apa-pbs-docs-citation-3"></a>([Szorc, n.d.](#apa-pbs-docs-reference)). Pure-Python packages work, but packages that ship compiled code may not.

### NixOS

NixOS does not keep a dynamic loader at the standard path, such as `/lib64/ld-linux-x86-64.so.2`, because its loader lives in the Nix store. The glibc builds expect the standard path, so on a default NixOS system running a runtime fails with a "No such file or directory" error, even though the file exists. Enabling nix-ld in the system configuration places a shim loader at the standard path and lets such binaries run unmodified <a name="apa-nix-ld-citation"></a>([nix-community, n.d.](#apa-nix-ld-reference)):

```nix
programs.nix-ld.enable = true;
```

The musl builds do not need the loader, but their limit on compiled extension modules makes nix-ld the recommended route. The wrappers need only `/bin/sh`, which NixOS provides.

## Collection-wide implications

Adopting this proposal implies the following changes to the OSAT user-space installation specification and the other managers <a name="apa-osat-spec-citation-2"></a>([Steel, 2026a](#apa-osat-spec-reference)):

- Record `-manager` as the target management identifier, and `manage-<name>` as the command pattern.
- Define that each manager installs itself under `<identifier>/manage-<name>/<version>/` and is reached through its own alias.
- Define gettext as the translation mechanism, with catalogs versioned alongside each manager.
- Define aliases, `--alias`, the alias record in the pointer file, and the rule that a manager never silently overwrites a file it did not write.
- Define `--switch` as taking a full version in every manager.
- Use "default", "installed" and "archived" in status output, replacing "active".
- Place the version pointer in `%LOCALAPPDATA%\<identifier>\` on Windows.

## License

This document, *Proposal: osat-manager-python Layout, Lifecycle and Aliases*, by **Christopher Steel**, with AI assistance from **Claude Opus 5.5 (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Resources

### OSAT collection

- [OSAT user-space installation specification](#apa-osat-spec-reference)
- [osat-fluent-restic-tool](#apa-restic-tool-reference)

### Python runtimes and packaging

- [python-build-standalone](#apa-pbs-repo-reference)
- [python-build-standalone: Running distributions](#apa-pbs-docs-reference)
- [Externally managed environments](#apa-pypa-em-reference)
- [uv: Python versions](#apa-uv-python-versions-reference)
- [Anaconda: Protected base installers](#apa-anaconda-pbe-reference)

### Platforms

- [Apple: BSD overview](#apa-apple-bsd-reference)
- [nix-ld](#apa-nix-ld-reference)

## References

<a name="apa-anaconda-pbe-reference"></a>Anaconda. (n.d.). *Protected base installers*. Anaconda documentation. https://www.anaconda.com/docs/getting-started/protected-base-beta
[Return to citation](#apa-anaconda-pbe-citation)

<a name="apa-apple-bsd-reference"></a>Apple. (n.d.). *BSD overview*. Kernel programming guide. Apple Developer Documentation Archive. https://developer.apple.com/library/content/documentation/Darwin/Conceptual/KernelProgramming/BSD/BSD.html
[Return to citation](#apa-apple-bsd-citation)

<a name="apa-uv-python-versions-reference"></a>Astral. (n.d.-a). *Python versions*. uv documentation. https://docs.astral.sh/uv/concepts/python-versions/
[Return to citation](#apa-uv-python-versions-citation)

<a name="apa-pbs-repo-reference"></a>Astral. (n.d.-b). *python-build-standalone* [Computer software]. GitHub. https://github.com/astral-sh/python-build-standalone
[Return to citation](#apa-pbs-repo-citation)

<a name="apa-nix-ld-reference"></a>nix-community. (n.d.). *nix-ld* [Computer software]. GitHub. https://github.com/nix-community/nix-ld
[Return to citation](#apa-nix-ld-citation)

<a name="apa-pypa-em-reference"></a>Python Packaging Authority. (n.d.). *Externally managed environments*. Python Packaging User Guide. https://packaging.python.org/en/latest/specifications/externally-managed-environments/
[Return to citation](#apa-pypa-em-citation)

<a name="apa-osat-spec-reference"></a>Steel, C. (2026a). *OSAT user-space installation specification* (Version 0.2.0). GitHub. https://github.com/steelcj/osat-fluent
[Return to citation](#apa-osat-spec-citation)

<a name="apa-restic-tool-reference"></a>Steel, C. (2026b). *osat-fluent-restic-tool* [Computer software]. GitHub. https://github.com/steelcj/osat-fluent-restic-tool
[Return to citation](#apa-restic-tool-citation)

<a name="apa-pbs-docs-reference"></a>Szorc, G. (n.d.). *Running distributions*. python-build-standalone documentation. https://gregoryszorc.com/docs/python-build-standalone/main/running.html
[Return to citation](#apa-pbs-docs-citation)

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.6.0 | Draft | Restructured to the technical documentation guide: the old implementation described, proposed changes presented as the new implementation, alternatives considered recorded for each decision, and a Contracts between components section defining the pointer file, alias wrappers, PROVENANCE, runtimes used by other managers, and operator output and logging; alias wrappers aligned with restic-tool's template header and sourcing order; Implementation section added |
| 0.5.1 | Draft | Conformance pass against the repository's markdown defaults and the versioned-documents style guide: Dublin Core frontmatter, Style Guide line naming the technical guide, Abstract, Sources and Acknowledgements, Resources, Citation Anchor Pairs in the house format, canonical closing sequence, code documentation license template; content unchanged |
| 0.5.0 | Draft | Decisions for the reference implementation: repository renamed to osat-manager-python with 0.3.0 as its first release; management identifier and command separated, with `manage-python` and the `manage-<name>` pattern; the manager installs itself, is reached through its own alias and runs on the default runtime; Python 3.8 floor for first installs on Linux and macOS; gettext translations and their locations; `unittest` and end-to-end testing; change from 0.2.0's versioned-only wrappers explained |
| 0.4.0 | Draft | Versions side by side note, including why the interpreter keeps its minor-version name. Supported platforms defined as those python-build-standalone publishes, checked against release 20260929, with the absence of BSD builds and the difference between macOS and the BSDs explained. Windows ARM64 and Linux ARM64 musl added to runtime selection. NixOS note and test matrix line. musl note expanded with the static-linking limit. References added for Apple, nix-ld and the python-build-standalone documentation |
| 0.3.0 | Draft | Platforms section: runtime selection by platform triple, alias wrappers for POSIX and Windows, PATH per platform. Alias names recorded in the pointer so renames survive installs and switches. XDG overrides respected on Linux and macOS. Testing covers every platform, with untested platforms declared in release notes. Notes for fresh Linux accounts, the system python3, Rosetta and musl |
| 0.2.0 | Draft | Design principle added: architecture for everyday scenarios, edge cases as notes. `--switch` takes a full version in every manager. Aliases introduced, with `--alias` for renaming, replacing ownership reporting. Status output uses an aliases row. Pointer keyed by minor line so renames never change it. uv, Store alias, venv and roaming-profile material moved to notes; venv migration deferred to the road to 1.0.0. References checked |
| 0.1.0 | Draft | Initial proposal from Windows testing of osat-fluent-python-tool 0.2.0 |
