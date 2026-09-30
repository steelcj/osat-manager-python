---
dc:title: "Installing manage-python on Windows with Command Prompt"
dcterms:version: "0.1.1"
dc:creator: "Christopher Steel"
dc:contributor: "Claude Opus 5.5 (Anthropic)"
dc:description: "Step-by-step guide to downloading, verifying and installing osat-manager-python 1.0.2 on Windows 11 from Command Prompt, through to installing and switching to a second Python version."
dcterms:created: "2026-09-29"
dcterms:modified: "2026-09-29"
dc:format: "text/markdown"
dc:language: "en"
sat:language_bcp47: "en"
dc:identifier: "installing-manage-python-on-windows-with-command-prompt"
dcterms:rightsHolder: "Christopher Steel"
dc:rights: >
  Copyright 2026 Christopher Steel.
  SPDX-License-Identifier: GPL-3.0-or-later
sat:uuid: ""
sat:repository: "osat-manager-python"
sat:path: "en/docs/guides/"
sat:version_at_creation: "0.4.0"
sat:migration_status: pre-sat
sat:changelog:
  - version: "0.1.1"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Corrections from walking through the guide on Windows 11: how to
      tell Command Prompt from PowerShell, opening Command Prompt from the
      Start menu rather than from inside PowerShell, PowerShell
      equivalents for the commands that differ, and a troubleshooting
      entry for "Get-FileHash is not recognized" in release 1.0.2.
  - version: "0.1.0"
    date: "2026-09-29"
    author: "Christopher Steel"
    notes: >
      Initial guide, based on installing osat-manager-python 1.0.2 on a
      Windows 11 virtual machine from Command Prompt.
---

# Installing manage-python on Windows with Command Prompt

Version: 0.1.1
Status: Draft
Style Guide: style-guide--plain-language-for-general-audiences

## Abstract

This guide walks through installing osat-manager-python on Windows 11 using only Command Prompt and tools that come with Windows. It covers downloading the release, checking that the download is genuine, installing Python with the manager, checking that everything works, and adding a second Python version and switching between the two. No administrator rights are needed at any step.

## Sources and Acknowledgements

The steps follow the design in the osat-manager-python proposal <a name="apa-omp-proposal-citation"></a>([Steel, 2026](#apa-omp-proposal-reference)) and were confirmed by installing release 1.0.2 on a Windows 11 virtual machine on 2026-09-29. The guide was written with AI assistance from Claude Opus 5.5 (Anthropic).

## What you need

- Windows 10 version 1803 or later, or Windows 11. These include `curl.exe`, `tar.exe` and `certutil`, the three tools this guide uses.
- An internet connection for the download and the first install.
- About 150 MB of free space for the manager and two Python versions.

You do not need Python already installed, and you do not need administrator rights. Run every step from an ordinary Command Prompt window, not one opened with "Run as administrator"; the manager refuses to make changes from an administrator window.

## Open Command Prompt

Press the Windows key, type `cmd`, and choose **Command Prompt** from the results. The commands below are typed or pasted into this window, one block at a time.

### Which window am I in?

Look at the prompt at the start of the line:

- `C:\Users\you>` is Command Prompt. This guide is written for it.
- `PS C:\Users\you>` is PowerShell. Windows Terminal often opens PowerShell by default, and the Command Prompt commands in this guide do not work there.

If you are in PowerShell, open Command Prompt from the Start menu as described above. Do not type `cmd` inside the PowerShell window to switch: the Command Prompt that starts that way inherits PowerShell's settings, and with release 1.0.2 the installer can then fail (see "Get-FileHash is not recognized" under If something goes wrong). If you prefer to stay in PowerShell, the sections below give PowerShell versions of the commands that differ.

## Download the release

Each release publishes two files on its GitHub release page: the release archive and a `SHA256SUMS` file containing the archive's checksum. We download both into a new folder:

```bat
cd /d "%USERPROFILE%\Downloads"
mkdir osat-manager-python-1.0.2-download
cd osat-manager-python-1.0.2-download
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/download/v1.0.2/osat-manager-python-1.0.2.tar.gz
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/download/v1.0.2/SHA256SUMS
```

In PowerShell, the first line is different; the rest are the same:

```powershell
Set-Location "$env:USERPROFILE\Downloads"
```

We use these two files rather than the "Source code (zip)" link on the release page. GitHub generates that zip on request and publishes no checksum for it, so there is nothing to check it against.

## Check the download

The checksum proves the archive you downloaded is exactly the one that was published. These commands compare the checksum in `SHA256SUMS` with the checksum of the file on your disk:

```bat
for /f "tokens=1" %h in (SHA256SUMS) do set EXPECTED=%h
for /f "tokens=*" %h in ('certutil -hashfile osat-manager-python-1.0.2.tar.gz SHA256 ^| findstr /v ":"') do set ACTUAL=%h
if /i "%EXPECTED%"=="%ACTUAL%" (echo Checksum OK) else (echo Checksum MISMATCH, do not continue)
```

You should see `Checksum OK`. If you see `Checksum MISMATCH`, delete both files and download them again; if it happens again, stop and report it on the project's GitHub page.

These commands are written for typing into Command Prompt. If you put them in a `.bat` file instead, write `%%h` in place of `%h`.

In PowerShell, use these instead:

```powershell
$expected = ((Get-Content SHA256SUMS -TotalCount 1) -split '\s+')[0]
$actual = (Get-FileHash osat-manager-python-1.0.2.tar.gz -Algorithm SHA256).Hash
if ($actual -eq $expected) { "Checksum OK" } else { "Checksum MISMATCH, do not continue" }
```

PowerShell's `-eq` ignores case, which matters because `Get-FileHash` prints the checksum in capital letters and `SHA256SUMS` uses lower case.

## Unpack the release

```bat
tar -xzf osat-manager-python-1.0.2.tar.gz
cd osat-manager-python-1.0.2
```

## Install

```bat
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer is a PowerShell script. Windows often refuses to run PowerShell scripts by default, and it refuses scripts downloaded through a web browser even more often, so this command asks PowerShell to run this one script without changing any settings <a name="apa-ms-execution-policies-citation"></a>([Microsoft, n.d.](#apa-ms-execution-policies-reference)). Typing `.\install.ps1` on its own in Command Prompt does not run it; Windows opens the file instead, usually with a security warning.

The installer downloads a small temporary copy of Python, uses it to run the manager, and deletes it afterwards. The manager then chooses the newest stable Python version, checks its download, and installs it. The output looks like this, with version numbers that may differ from yours:

```text
[install.ps1] downloading bootstrap Python (x86_64-pc-windows-msvc)...
[install.ps1] verifying checksum...
[install.ps1] extracting...
[install.ps1] bootstrap Python ready. Handing off to manage-python.py for the real, verified install...
[manage-python] selected CPython 3.14.7+20260929 (x86_64-pc-windows-msvc)
[manage-python] downloading SHA256SUMS for release 20260929...
[manage-python] downloading cpython-3.14.7+20260929-x86_64-pc-windows-msvc-install_only_stripped.tar.gz...
[manage-python] verified SHA-256
[manage-python] installing to %LOCALAPPDATA%\python-manager\3.14.7...
[manage-python] manager 1.0.2 installed: %LOCALAPPDATA%\python-manager\manage-python\1.0.2
[manage-python] alias written: %LOCALAPPDATA%\Programs\python.cmd
[manage-python] alias written: %LOCALAPPDATA%\Programs\python.ps1
[manage-python] alias written: %LOCALAPPDATA%\Programs\python3.14.cmd
[manage-python] alias written: %LOCALAPPDATA%\Programs\python3.14.ps1
[manage-python] alias written: %LOCALAPPDATA%\Programs\manage-python.cmd
[manage-python] alias written: %LOCALAPPDATA%\Programs\manage-python.ps1
[manage-python] CPython 3.14.7 installed; python and python3.14 now run it
[manage-python] Added %LOCALAPPDATA%\Programs to the start of your user PATH (HKCU\Environment\Path) so the manager's commands are found. Open a new terminal to use them.
[manage-python] Your previous PATH was saved to %LOCALAPPDATA%\python-manager\logs\path-backup-20260929T234226Z.txt. To undo, run: rundll32 sysdm.cpl,EditEnvironmentVariables  then select Path under your user variables and remove that entry.
[install.ps1] done (bootstrap Python will now be cleaned up; it was never the permanent install).
```

The last two `[manage-python]` lines tell you the installer added one folder to the start of your PATH, the list of places Windows looks for commands, and where it saved a copy of your previous PATH. The next section explains why.

## Open a new Command Prompt

Windows only gives the new PATH to windows opened after the change. Close this Command Prompt and open a new one before continuing.

## Check that it works

In the new window:

```bat
where.exe python
python --version
python3.14 --version
manage-python --status
```

`where.exe python` should list `%LOCALAPPDATA%\Programs\python.cmd` first. You may also see `WindowsApps\python.exe` listed after it. That is a shortcut Windows includes to open the Microsoft Store; because the manager's folder comes first, your `python` command runs the installed Python instead.

`manage-python --status` shows what is installed:

```text
manage-python 1.0.2

3.14
  aliases     python3.14  python
    default     3.14.7
```

This means Python 3.14.7 is installed, and both `python3.14` and `python` run it.

## Install a second Python version

To add Python 3.13 alongside 3.14:

```bat
manage-python --install 3.13
```

The manager installs the newest 3.13 version and switches to it, the same way every install does. `python` now runs 3.13, while `python3.14` still runs 3.14. Check with:

```bat
python --version
python3.13 --version
python3.14 --version
manage-python --status
```

The status now shows both versions, with `python` listed under 3.13:

```text
manage-python 1.0.2

3.13
  aliases     python3.13  python
    default     3.13.15

3.14
  aliases     python3.14
    default     3.14.7
```

Your 3.13 version number may be newer than 3.13.15.

## Switch between versions

To make `python` run 3.14 again, switch to its full version number:

```bat
manage-python --switch 3.14.7
python --version
```

Switching is instant. Nothing is downloaded or removed, and both versions stay installed, so you can switch back to 3.13 the same way at any time.

## Next steps

Install packages into a virtual environment rather than into an installed Python. The manager protects each installed Python, so `pip install` into one of them is refused with a message pointing to virtual environments. To create and use one for a project:

```bat
python3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install requests
```

Inside an activated virtual environment, use `python`, not `python3.14`, so that commands run the environment's Python.

## If something goes wrong

**`'manage-python' is not recognized` or `'python' is not recognized`.** Open a new Command Prompt window. Windows gives the updated PATH only to windows opened after the install.

**`python` opens the Microsoft Store or says Python was not found.** The Store shortcut is being found before the manager's folder, usually because the window was opened before the install. Open a new window and run `where.exe python`. If `%LOCALAPPDATA%\Programs\python.cmd` is still not listed first, turn off the shortcut under Settings > Apps > Advanced app settings > App execution aliases.

**`python3` opens the Microsoft Store.** This is expected. The manager does not create a `python3` command; use `python` or a versioned command such as `python3.14`.

**The installer stops with "Get-FileHash is not recognized".** This happens with release 1.0.2 when Command Prompt was started from inside a PowerShell 7 window, for example by typing `cmd` there. The installer runs in the older Windows PowerShell, which then looks for its commands in PowerShell 7's folders. Open a fresh Command Prompt from the Start menu and run the install command again, or clear the inherited setting first in the same window:

```bat
set "PSModulePath="
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The next release computes the checksum without `Get-FileHash`, so this no longer happens.

**The manager refuses to run from an administrator window.** Open an ordinary Command Prompt and run the command again.

**Undoing the PATH change.** Run `rundll32 sysdm.cpl,EditEnvironmentVariables`, select Path under your user variables, and remove the `%LOCALAPPDATA%\Programs` entry. The PATH you had before is saved in the backup file named during the install, in `%LOCALAPPDATA%\python-manager\logs\`.

## License

This document, *Installing manage-python on Windows with Command Prompt*, by **Christopher Steel**, with AI assistance from **Claude Opus 5.5 (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Resources

### osat-manager-python

- [Proposal: osat-manager-python Layout, Lifecycle and Aliases](#apa-omp-proposal-reference)

### Windows

- [about_Execution_Policies](#apa-ms-execution-policies-reference)

## References

<a name="apa-ms-execution-policies-reference"></a>Microsoft. (n.d.). *about_Execution_Policies*. Microsoft Learn. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
[Return to citation](#apa-ms-execution-policies-citation)

<a name="apa-omp-proposal-reference"></a>Steel, C. (2026). *Proposal: osat-manager-python layout, lifecycle and aliases* (Version 0.7.0). GitHub. https://github.com/steelcj/osat-manager-python
[Return to citation](#apa-omp-proposal-citation)

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.1.1 | Draft | Corrections from walking through the guide on Windows 11: telling Command Prompt from PowerShell, opening Command Prompt from the Start menu, PowerShell equivalents for the commands that differ, and a troubleshooting entry for "Get-FileHash is not recognized" in release 1.0.2 |
| 0.1.0 | Draft | Initial guide, based on installing osat-manager-python 1.0.2 on a Windows 11 virtual machine from Command Prompt |
