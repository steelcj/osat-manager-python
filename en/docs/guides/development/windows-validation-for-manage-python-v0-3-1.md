---
dc:title: "Windows Validation for manage-python"
dcterms:version: "0.3.1"
dc:creator: "Christopher Steel"
dc:contributor: "Claude Opus 5.5 (Anthropic)"
dc:description: "How to run validate-windows.ps1 on a fresh Windows 11 VM snapshot, the manual steps it cannot automate, and what to bring back."
dcterms:created: "2026-09-29"
dcterms:modified: "2026-09-29"
dc:format: "text/markdown"
dc:language: "en"
sat:language_bcp47: "en"
dc:identifier: "windows-validation-for-manage-python"
dcterms:rightsHolder: "Christopher Steel"
dc:rights: >
  Copyright 2026 Christopher Steel.
  SPDX-License-Identifier: GPL-3.0-or-later
sat:uuid: ""
sat:repository: "osat-manager-python"
sat:path: "en/docs/guides/development/"
sat:version_at_creation: "0.4.0"
sat:migration_status: pre-sat
sat:changelog:
  - version: "0.3.1"
    date: "2026-09-30"
    author: "Christopher Steel"
    notes: >
      The older runtime is installed pinned (-OlderBuild), so only the
      first install needs the GitHub API. A check that needs a runtime an
      earlier step failed to install reports BLOCKED with the cause
      instead of FAIL. Result and exit code explained.
  - version: "0.3.0"
    date: "2026-09-30"
    author: "Christopher Steel"
    notes: >
      Windows aliases are .cmd files only from this release: the script
      checks the .cmd aliases from cmd.exe, Windows PowerShell 5.1 and
      PowerShell 7 under the default execution policy, argument
      pass-through and exit codes through the .cmd layer from PowerShell,
      the pip message, and the removal of .ps1 aliases written by 1.0.2.
      The pointer is python-manager.env.cmd only: section 13 also checks
      that the 1.0.2 python-manager.env.ps1 is deleted and that an operator
      env.ps1 is left with a single warning.
      Section 11 recognises PowerShell 7's module paths, the Store install
      included. Running it from Command Prompt is documented; manual step
      M3 rewritten for the .cmd alias.
  - version: "0.2.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Added the scenario found on the Windows VM: install.ps1 run by
      Windows PowerShell 5.1 started from a Command Prompt opened inside
      PowerShell 7, which inherits PowerShell 7's PSModulePath. Section 11
      of the script and manual step M6.
  - version: "0.1.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: "Initial draft: running validate-windows.ps1 from a fresh Windows 11 snapshot, manual steps, and the report to bring back."
---

# Windows Validation for manage-python

Version: 0.3.1
Status: Draft
Style Guide: style-guide--technical-documentation-for-technologists

## Abstract

`validate-windows.ps1` validates a manage-python release on a real Windows 11 machine under Windows PowerShell 5.1. It runs the bootstrap through `install.ps1`, the user PATH write, the `.cmd` aliases from `cmd.exe`, Windows PowerShell 5.1 and PowerShell 7 under the default execution policy, pip and venv behaviour, switch, rename, remove and an offline restore, `install.ps1` run from a Command Prompt opened inside PowerShell 7, and the retirement of the `.ps1` aliases and PowerShell pointer left by 1.0.2. It writes one report file to bring back. A few behaviours need a person at the keyboard; they are listed below and in the report.

## Before you start

- Use a Windows 11 VM with a fresh snapshot. The script changes the account it runs under: it installs runtimes, writes aliases and prepends `%LOCALAPPDATA%\Programs` to the user PATH. Revert the snapshot afterwards.
- Sign in as an ordinary user, not an administrator.
- The VM needs internet access. The run downloads a bootstrap Python and three runtimes, about 130 MB.

## Running it

1. Download the release tarball and extract it: `tar -xzf osat-manager-python-<version>.tar.gz`.
2. Copy `validate-windows.ps1` into the extracted folder, next to `install.ps1`, if the release does not include it.
3. Open Command Prompt or Windows PowerShell, change to that folder and run the command below. It is the same in both, and it starts Windows PowerShell 5.1 (`powershell.exe`) whichever window it is typed in:

   ```bat
   powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-windows.ps1 -FreshSnapshot
   ```

Only the first install asks the GitHub API which release to use. The older 3.12 runtime is installed as a pinned build, `3.12.13+20260807` by default, which needs no API call; pass `-OlderBuild <version>+<build>` to use another. The manager retries GitHub server errors and reset connections itself, so a brief GitHub outage shows up as retry lines in the captured output rather than as a failure.

If an install still fails, every check that needs that runtime reports `BLOCKED`, with the install's error as the cause, instead of failing in turn. A `BLOCKED` check was not tested, so the run as a whole is not a pass: the script exits with 1 when any check failed or was blocked, and the `RESULT` lines list both. If the first install fails, nothing after it can be checked and the script stops.

The script itself refuses to run under PowerShell 7, from an elevated window, without `-FreshSnapshot`, or if `%LOCALAPPDATA%\python-manager` already exists. Each check prints `PASS` or `FAIL`, facts print `NOTE`, and the last line names the report file, `validate-windows-report-<computer>-<UTC>.txt`.

## Windows PowerShell 5.1 started from inside PowerShell 7

Windows PowerShell 5.1 started from a Command Prompt that was itself opened inside PowerShell 7 inherits PowerShell 7's `PSModulePath`. It then cannot load cmdlets that come through the module path, such as `Get-FileHash`, which is how `install.ps1` failed on the first VM run. `install.ps1` now uses only cmdlets built into 5.1 and .NET, and a unit test keeps it and the other PowerShell scripts that way.

Section 11 of the script reproduces the chain when PowerShell 7 (`pwsh.exe`) is installed: PowerShell 7, then `cmd.exe`, then `powershell.exe` running `install.ps1`. It notes the `PSModulePath` that 5.1 saw, so the report shows whether the scenario was reproduced. Without PowerShell 7 the section is skipped; use manual step M6.

## Aliases are .cmd files

From this release the manager writes each Windows alias as a `.cmd` file only. The 1.0.2 validation showed why: Windows PowerShell 5.1's default execution policy, Restricted on Windows 11, blocks `.ps1` scripts, PowerShell picks `python3.12.ps1` over `python3.12.cmd` when both exist, and it does not fall back to the `.cmd`. Sections 5, 6 and 12 run the aliases by name from `cmd.exe`, Windows PowerShell 5.1 and PowerShell 7 (when installed), with each PowerShell session at the machine's default execution policy. Section 5 also notes what Python receives for `100%`, `a^b`, `%OSAT_KEEP%` and `!x!`, which `cmd.exe` may reinterpret. The pointer is likewise `python-manager.env.cmd` only, and the operator environment on Windows is `env.cmd` only. Section 13 plants a `.ps1` alias as 1.0.2 wrote it and one written by someone else, and checks that `--switch` removes the first and leaves the second with a warning. It then plants the 1.0.2 `python-manager.env.ps1` and an operator `env.ps1`, and checks that `--switch` deletes the first, leaves the second, and warns once that it is no longer read.

## Manual steps

Do these after the script finishes, and write each result into the report's manual steps section.

- **M1:** open a new terminal from the Start menu and run `where.exe python`, `Get-Command python -All` and `python --version`. The manager's aliases should come before the Microsoft Store alias.
- **M2:** in `cmd.exe`, start `python`, press Ctrl+C at the prompt, then run `python -c "import time; time.sleep(30)"` and press Ctrl+C. Record whether "Terminate batch job (Y/N)?" appears and what each answer does.
- **M3:** repeat M2 in Windows PowerShell 5.1, then in PowerShell 7, calling `python` by name, which runs the `.cmd` alias. Record whether "Terminate batch job (Y/N)?" appears and whether the PowerShell prompt comes back normally afterwards.
- **M4:** run `rundll32 sysdm.cpl,EditEnvironmentVariables` and confirm the user Path shows `%LOCALAPPDATA%\Programs` first.
- **M5:** sign out and back in, and confirm `python` and `manage-python` still run in a new terminal.
- **M6:** only if section 11 was skipped. Install PowerShell 7, open it, run `cmd`, then from the release folder run `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 --install <a version shown by --status>`. Record whether it finishes without "is not recognized", and what `powershell -NoProfile -Command "$env:PSModulePath"` prints from that same Command Prompt.

## What to bring back

The report file. It holds every check, the notes, the captured output of each step, `manage-python.log`, the PATH backup, and your manual results.

## License

This document, *Windows Validation for manage-python*, by **Christopher Steel**, with AI assistance from **Claude Opus 5.5 (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.3.1 | Draft | Older runtime installed pinned (`-OlderBuild`); checks that need a runtime an earlier step failed to install report `BLOCKED` with the cause; result and exit code explained |
| 0.3.0 | Draft | Windows aliases are `.cmd` files only: checks from `cmd.exe`, Windows PowerShell 5.1 and PowerShell 7 under the default execution policy, argument pass-through and exit codes through the `.cmd` layer, the pip message, and retirement of the `.ps1` aliases and PowerShell pointer left by 1.0.2; section 11 recognises PowerShell 7's module paths, the Store install included; running from Command Prompt documented; M3 rewritten |
| 0.2.0 | Draft | Added the `install.ps1` scenario from a Command Prompt opened inside PowerShell 7: section 11 of the script and manual step M6 |
| 0.1.0 | Draft | Initial draft: running validate-windows.ps1 from a fresh Windows 11 snapshot, manual steps, and the report to bring back |
