---
dc:title: "Windows Validation for manage-python"
dcterms:version: "0.4.0"
dc:creator: "Christopher Steel"
dc:contributor: "Claude Opus 5.5 (Anthropic)"
dc:description: "How to run validate-windows.ps1 and the unit tests on a fresh Windows 11 VM snapshot, from getting the code to bringing the results back, including the manual steps and how to read the report."
dcterms:created: "2026-09-29"
dcterms:modified: "2026-09-30"
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
  - version: "0.4.0"
    date: "2026-09-30"
    author: "Christopher Steel"
    notes: >
      Rewritten as a complete procedure from the VM runs of 2026-09-29:
      preparing and restoring the snapshot, getting the code from a branch
      or a release into a new folder, choosing the right window, the parse
      check, running the validation and then the unit tests, the manual
      steps, reading PASS, FAIL, BLOCKED and NOTE, bringing the results
      back by copy and paste or over the network, cleaning up, and
      troubleshooting the problems met during those runs.
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
      Windows aliases are .cmd files only from this release, with checks
      from cmd.exe, Windows PowerShell 5.1 and PowerShell 7 under the
      default execution policy, and retirement of the .ps1 aliases and
      PowerShell pointer left by 1.0.2.
  - version: "0.2.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Added the install.ps1 scenario from a Command Prompt opened inside
      PowerShell 7: section 11 of the script and manual step M6.
  - version: "0.1.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: "Initial draft."
---

# Windows Validation for manage-python

Version: 0.4.0
Status: Draft
Style Guide: style-guide--technical-documentation-for-technologists

## Abstract

This guide is the complete procedure for validating manage-python on a Windows 11 virtual machine: preparing a fresh snapshot, getting the code under test, running `validate-windows.ps1` and the unit tests, performing the manual steps, reading the results, and bringing them back to the development machine. It records the practical lessons of the first VM runs, among them which window to use, why every run starts from a new folder, and how to get results off the VM when networking between host and guest is not available.

## Notes

* We take extra care when testing osat-manager-python because:
  * osat-manager-python is required for other osat managers
  * Any major osat-manager specifications builds start here

## What the validation covers

`validate-windows.ps1` runs under Windows PowerShell 5.1, the version every Windows 11 machine has. It covers the bootstrap through `install.ps1`, the user PATH write and its backup, the `.cmd` aliases from `cmd.exe`, Windows PowerShell 5.1 and PowerShell 7 under the default execution policy, argument and exit code pass-through, pip and venv behaviour, switch, rename, remove and an offline restore, `install.ps1` run from a Command Prompt opened inside PowerShell 7, and the retirement of the `.ps1` files left by release 1.0.2.

The unit tests, `test_manage_python.py`, cover the manager's logic. They download nothing and write only to scratch directories, and on Windows they complement the validation rather than replace it.

A complete run means both: the validation report with its manual steps filled in, and the unit test output.

## Before you start

You need:

- A Windows 11 virtual machine with a snapshot to return to. Every validation run starts from that snapshot, because the script changes the account it runs under and refuses to run if `%LOCALAPPDATA%\python-manager` already exists.
- An ordinary, non-administrator window for everything except the optional firewall rule described under bringing results back. The script and the manager both refuse to run elevated.
- Internet access on the VM. A run downloads a bootstrap Python and three runtimes, about 130 MB, and takes about four minutes.
- Optionally, PowerShell 7. With it installed, section 11 and the PowerShell 7 checks run; without it they are skipped and manual step M6 applies.

The VM has no Python of its own. The validation installs one, and the unit tests use it afterwards, so the order below matters.

## Development cycle

When you are done testing in the Windows VM:

```bash
incus stop windows --timeout 120 || incus stop windows --force
```

Spinning up a pristine vm for starting a new te

```bash
incus snapshot restore windows pristine-windows-11-002
incus start windows
incus console windows --type=vga
```

`--no-expiry` keeps the baseline from being pruned if scheduled snapshots are ever configured on the instance.

## Opening the right window

Open Command Prompt from the Start menu: press the Windows key, type `cmd`, and choose Command Prompt. The prompt reads `C:\Users\<you>>`, with no `PS` in front.

Do not type `cmd` inside a PowerShell window to get one. A Command Prompt started that way inherits PowerShell 7's settings, which is a scenario the validation tests deliberately in section 11, not the environment to run it from. A Windows Terminal window often opens PowerShell by default; check the prompt before starting.

## Getting the code

Always extract into a new folder. `tar` writes over an existing folder without removing files that have since been deleted, so a reused folder can mix two versions of the code.

### Validating a branch before release

Replace `<branch>` with the branch name, for example `windows-test-fixes`, and `<run>` with a name for this run, for example the commit you are testing:

Check your branch

```bash
git status
```

Find the branch, for example:

```bash
windows-test-fixes
```



```bat
cd /d "%USERPROFILE%\Downloads"
mkdir osat-run-test-001
cd osat-run-test-001
curl.exe -fLo windows-test-fixes.tar.gz https://github.com/steelcj/osat-manager-python/archive/refs/heads/windows-test-fixes.tar.gz
tar -xzf windows-test-fixes.tar.gz
cd osat-manager-python-windows-test-fixes
```

### Validating a published release

Replace `<version>` with the release version, for example `1.0.3`. The release publishes a `SHA256SUMS` file; check the archive against it before extracting:

```bat
cd /d "%USERPROFILE%\Downloads"
mkdir osat-release-<version>
cd osat-release-<version>
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/download/v<version>/osat-manager-python-<version>.tar.gz
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/download/v<version>/SHA256SUMS
for /f "tokens=1" %h in (SHA256SUMS) do set EXPECTED=%h
for /f "tokens=*" %h in ('certutil -hashfile osat-manager-python-<version>.tar.gz SHA256 ^| findstr /v ":"') do set ACTUAL=%h
if /i "%EXPECTED%"=="%ACTUAL%" (echo Checksum OK) else (echo Checksum MISMATCH, do not continue)
tar -xzf osat-manager-python-<version>.tar.gz
cd osat-manager-python-<version>
```

If the release does not include `validate-windows.ps1`, copy it into this folder, next to `install.ps1`.

## Checking the script parses

A script that fails to parse wastes a snapshot restore. Check it first; this makes no changes:

```bat
powershell -NoProfile -Command "$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\validate-windows.ps1), [ref]$null, [ref]$e); if ($e) { $e } else { 'parses cleanly' }"
```

Continue only if it prints `parses cleanly`.

## Running the validation

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-windows.ps1 -FreshSnapshot
```

Tail of validation output:

```cmd
...
[13 Files written by 1.0.2 for PowerShell are retired]
  PASS  --switch removes a .ps1 alias the manager wrote
  PASS  --switch leaves a .ps1 it did not write, with a warning
  PASS  --switch deletes the pointer's .ps1 copy
  PASS  the operator's env.ps1 is left in place
  PASS  a warning says env.ps1 is no longer read
  PASS  the warning is shown once

RESULT: all automated checks passed in 156 s. Complete the manual steps below.

Report: C:\Users\initial\Downloads\osat-run-test-001\osat-manager-python-windows-test-fixes\validate-windows-report-DESKTOP-VB8SQ0P-20260930T035225Z.txt
```

Use exactly this command. Typing `.\validate-windows.ps1` on its own opens the file in Command Prompt, and is blocked by the execution policy in PowerShell. `-ExecutionPolicy Bypass` applies to this one script and changes no settings. The command starts Windows PowerShell 5.1 whichever window it is typed in.

Only the first install asks the GitHub API which release to use. The older 3.12 runtime is installed as a pinned build, `3.12.13+20260807` by default, which needs no API call; pass `-OlderBuild <version>+<build>` to use another. The manager retries GitHub server errors and reset connections, so a brief GitHub outage appears as retry lines in the captured output rather than as a failure.

The last line printed names the report file, `validate-windows-report-<computer>-<UTC>.txt`, with its full path. Note it.

## Running the unit tests

The validation has now installed Python and added `%LOCALAPPDATA%\Programs` to the user PATH. **Close the window**, and **open a new Command Prompt from the Start menu** so it sees the new PATH

return to the same folder

```cmd
cd \Users\initial\Downloads\osat-run-test-001\osat-manager-python-windows-test-fixes
```

and run:

```bat
python test_manage_python.py -v > test-output.txt 2>&1
type test-output.txt | more
```

The last lines give the totals, for example `Ran 216 tests` followed by `OK (skipped=19)`. On Windows, skips are expected for tests that exercise Linux and macOS behaviour, tests that need `git`, which the VM does not have, the symbolic link test, which needs Developer Mode, and the test that reads the host's `/bin/sh`. Any `FAIL` or `ERROR` is a finding.

## Manual steps

These need a person at the keyboard. Do them after the unit tests and write each result into the report's manual steps section, which you can open with `notepad <report file>`.

- **M1:** open a new terminal from the Start menu and run `where.exe python`, then in PowerShell `Get-Command python -All`, then `python --version`. The manager's aliases should come before the Microsoft Store alias.
- **M2:** in `cmd.exe`, start `python`, press Ctrl+C at the prompt, then run `python -c "import time; time.sleep(30)"` and press Ctrl+C. Record whether "Terminate batch job (Y/N)?" appears and what each answer does.
- **M3:** repeat M2 in Windows PowerShell 5.1, then in PowerShell 7, calling `python` by name, which runs the `.cmd` alias. Record whether "Terminate batch job (Y/N)?" appears and whether the PowerShell prompt comes back normally.
- **M4:** run `rundll32 sysdm.cpl,EditEnvironmentVariables` and confirm the user Path shows `%LOCALAPPDATA%\Programs` first.
- **M5:** sign out and back in, and confirm `python` and `manage-python` still run in a new terminal.
- **M6:** only if section 11 was skipped. Install PowerShell 7, open it, run `cmd`, then from the code folder run `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 --install <a version shown by manage-python --status>`. Record whether it finishes without "is not recognized", and what `powershell -NoProfile -Command "$env:PSModulePath"` prints from that same Command Prompt.

## Reading the results

Each check in the report prints one of four words:

| Result | Meaning |
|---|---|
| `PASS` | The check ran and the behaviour was correct |
| `FAIL` | The check ran and the behaviour was wrong: a finding |
| `BLOCKED` | The check could not run because a runtime it needs failed to install; the cause is shown, and the check was not tested |
| `NOTE` | A recorded fact, not a check, such as the PATH value or which file a shell selected |

The `RESULT` line at the end lists failed and blocked checks separately. The script exits with 0 only when nothing failed or was blocked. A run with blocked checks is not a pass, even if nothing failed: fix the cause, usually a network or GitHub problem shown in the captured output, and run again from the snapshot.

A clean run is: `RESULT` with no failed or blocked checks, the unit tests ending in `OK`, and all manual steps recorded.

## Bringing the results back

Bring back the report file, with the manual steps filled in, and `test-output.txt`.

### Copy and paste

The simplest route, and the one that always works, is to print a file and copy it from the terminal:

```bat
type test-output.txt
```

If the VM viewer shares the clipboard with the host, which usually needs the SPICE guest tools in Windows, this copies the whole file in one step:

```bat
type test-output.txt | clip
```

### Over the network

If the host can reach the VM, Python's built-in web server can serve the files. Networking between host and guest depends on the host's configuration and does not always work; fall back to copy and paste if it does not.

1. Find the VM's address with `ipconfig | findstr IPv4`.
2. Allow the port through the Windows Firewall. This is the only step that needs an administrator window: press the Windows key, type `cmd`, and press Ctrl+Shift+Enter, then:

   ```bat
   netsh advfirewall firewall add rule name="osat test reports" dir=in action=allow protocol=TCP localport=8765
   ```

3. In an ordinary Command Prompt, in the folder holding the files:

   ```bat
   python -m http.server 8765 --bind 0.0.0.0
   ```

4. On the host, test with `curl`, since the Windows Firewall blocks ping even when this works:

   ```bash
   curl -O http://<vm-address>:8765/test-output.txt
   curl -O http://<vm-address>:8765/<report file name>
   ```

5. Stop the server with Ctrl+C and remove the rule from the administrator window:

   ```bat
   netsh advfirewall firewall delete rule name="osat test reports"
   ```

## Cleaning up

Restore the snapshot after the results are safely on the host. The run leaves runtimes, aliases and a PATH change behind, and the next run needs a clean account.

## Troubleshooting

**`.\validate-windows.ps1` opens the file, or reports that running scripts is disabled.** Run it with the full `powershell -NoProfile -ExecutionPolicy Bypass -File` command above.

**The script refuses to start.** It refuses under PowerShell 7, from an elevated window, without `-FreshSnapshot`, and when `%LOCALAPPDATA%\python-manager` already exists. The last usually means the snapshot was not restored.

**`python` is not recognized, or opens the Microsoft Store, after the validation.** The window was opened before the PATH change. Open a new Command Prompt from the Start menu.

**An install fails with a GitHub error and later checks report `BLOCKED`.** GitHub was unavailable for longer than the manager's retries cover. Restore the snapshot and run again later.

**`Get-FileHash is not recognized` during `install.ps1`.** This affected release 1.0.2 when Command Prompt was opened inside PowerShell 7. Later releases do not use `Get-FileHash`; if it appears, the code under test is older than expected, so check which folder you are in.

**The unit tests show an "Unsupported 16-Bit Application" dialog.** Earlier branches ran a stand-in interpreter that Windows cannot execute. Current code does not; if it appears, the code under test is older than expected.

## License

This document, *Windows Validation for manage-python*, by **Christopher Steel**, with AI assistance from **Claude Opus 5.5 (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.4.0 | Draft | Rewritten as a complete procedure from the VM runs of 2026-09-29: preparing and restoring the snapshot, getting the code from a branch or a release into a new folder, choosing the right window, the parse check, running the validation and then the unit tests, the manual steps, reading PASS, FAIL, BLOCKED and NOTE, bringing results back by copy and paste or over the network, cleaning up, and troubleshooting |
| 0.3.1 | Draft | Older runtime installed pinned (`-OlderBuild`); checks that need a runtime an earlier step failed to install report `BLOCKED` with the cause; result and exit code explained |
| 0.3.0 | Draft | Windows aliases are `.cmd` files only, with checks from `cmd.exe`, Windows PowerShell 5.1 and PowerShell 7 under the default execution policy, and retirement of the `.ps1` files left by 1.0.2 |
| 0.2.0 | Draft | Added the `install.ps1` scenario from a Command Prompt opened inside PowerShell 7: section 11 of the script and manual step M6 |
| 0.1.0 | Draft | Initial draft |
