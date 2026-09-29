---
dc:title: "Windows Validation for manage-python"
dcterms:version: "0.1.0"
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
  - version: "0.1.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: "Initial draft: running validate-windows.ps1 from a fresh Windows 11 snapshot, manual steps, and the report to bring back."
---

# Windows Validation for manage-python

Version: 0.1.0
Status: Draft
Style Guide: style-guide--technical-documentation-for-technologists

## Abstract

`validate-windows.ps1` validates a manage-python release on a real Windows 11 machine under Windows PowerShell 5.1. It runs the bootstrap through `install.ps1`, the user PATH write, the `.cmd` and `.ps1` aliases under `cmd.exe` and `powershell.exe`, command precedence under the default execution policy, pip and venv behaviour, and switch, rename, remove and an offline restore. It writes one report file to bring back. A few behaviours need a person at the keyboard; they are listed below and in the report.

## Before you start

- Use a Windows 11 VM with a fresh snapshot. The script changes the account it runs under: it installs runtimes, writes aliases and prepends `%LOCALAPPDATA%\Programs` to the user PATH. Revert the snapshot afterwards.
- Sign in as an ordinary user, not an administrator.
- The VM needs internet access. The run downloads a bootstrap Python and three runtimes, about 130 MB.

## Running it

1. Download the release tarball and extract it: `tar -xzf osat-manager-python-<version>.tar.gz`.
2. Copy `validate-windows.ps1` into the extracted folder, next to `install.ps1`, if the release does not include it.
3. Open Windows PowerShell 5.1 (`powershell.exe`, not `pwsh`), change to that folder and run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-windows.ps1 -FreshSnapshot
   ```

The script refuses to run under PowerShell 7, from an elevated window, without `-FreshSnapshot`, or if `%LOCALAPPDATA%\python-manager` already exists. Each check prints `PASS` or `FAIL`, facts print `NOTE`, and the last line names the report file, `validate-windows-report-<computer>-<UTC>.txt`.

## Manual steps

Do these after the script finishes, and write each result into the report's manual steps section.

- **M1:** open a new terminal from the Start menu and run `where.exe python`, `Get-Command python -All` and `python --version`. The manager's aliases should come before the Microsoft Store alias.
- **M2:** in `cmd.exe`, start `python`, press Ctrl+C at the prompt, then run `python -c "import time; time.sleep(30)"` and press Ctrl+C. Record whether "Terminate batch job (Y/N)?" appears and what each answer does.
- **M3:** repeat M2 in Windows PowerShell 5.1 with `python.ps1`, calling it by full path if PowerShell picks the `.cmd`. Afterwards `Get-ChildItem Env:PYTHON_MANAGER*` should list nothing.
- **M4:** run `rundll32 sysdm.cpl,EditEnvironmentVariables` and confirm the user Path shows `%LOCALAPPDATA%\Programs` first.
- **M5:** sign out and back in, and confirm `python` and `manage-python` still run in a new terminal.

## What to bring back

The report file. It holds every check, the notes, the captured output of each step, `manage-python.log`, the PATH backup, and your manual results.

## License

This document, *Windows Validation for manage-python*, by **Christopher Steel**, with AI assistance from **Claude Opus 5.5 (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.1.0 | Draft | Initial draft: running validate-windows.ps1 from a fresh Windows 11 snapshot, manual steps, and the report to bring back |
