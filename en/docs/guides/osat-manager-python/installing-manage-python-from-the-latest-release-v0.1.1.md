---
dc:title: "Installing manage-python from the Latest Release"
dcterms:version: "0.1.0"
dc:creator: "Christopher Steel"
dc:contributor: "Claude Opus 5.5 (Anthropic)"
dc:description: "Step-by-step guide to downloading, verifying and installing the latest release of osat-manager-python on Linux, macOS and Windows, using commands that keep working when a new release is published."
dcterms:created: "2026-09-30"
dcterms:modified: "2026-09-30"
dc:format: "text/markdown"
dc:language: "en"
sat:language_bcp47: "en"
dc:identifier: "installing-manage-python-from-the-latest-release"
dcterms:rightsHolder: "Christopher Steel"
dc:rights: >
  Copyright 2026 Christopher Steel.
  SPDX-License-Identifier: GPL-3.0-or-later
sat:uuid: ""
sat:repository: "osat-manager-python"
sat:path: "en/docs/guides/osat-manager-python/"
sat:version_at_creation: "0.4.0"
sat:migration_status: pre-sat
sat:changelog:
  - version: "0.1.0"
    date: "2026-09-30"
    author: "Christopher Steel"
    notes: >
      Initial guide covering Linux, macOS and Windows, written against
      release 1.0.2, with download commands that follow the latest
      release rather than a fixed version.
---

# Installing manage-python from the Latest Release

Version: 0.1.0
Status: Draft
Style Guide: style-guide--plain-language-for-general-audiences

## Abstract

This guide installs the newest published release of osat-manager-python on Linux, macOS or Windows. The commands never name a version number: they ask GitHub for the latest release, read the archive's name from the release's checksum file, download it, and check it before anything is installed. The same commands therefore keep working when a new release comes out. No administrator rights are needed at any step.

## Sources and Acknowledgements

The steps follow the design in the osat-manager-python proposal <a name="apa-omp-proposal-citation"></a>([Steel, 2026](#apa-omp-proposal-reference)) and the Windows steps build on the guide *Installing manage-python on Windows with Command Prompt*. Downloading through the latest-release address uses a feature GitHub documents for linking to release files <a name="apa-gh-linking-releases-citation"></a>([GitHub, n.d.](#apa-gh-linking-releases-reference)). The guide was written against release 1.0.2 with AI assistance from Claude Opus 5.5 (Anthropic).

## Before you start

**What "latest" means.** GitHub's latest release is the newest release that is not marked as a pre-release. At the time of writing that is 1.0.2.

**What has been tested.** Release 1.0.2 is verified end to end on Linux x86-64, and its Windows install was walked through on Windows 11. macOS is supported by the installer but not yet verified. Check the Status section of the project's README for the current picture.

**What you need.**

- Linux (x86-64 or ARM64) or macOS (Intel or Apple silicon) with `curl` and `tar`, which come with both systems. On Linux you also need `gzip` and `sha256sum`, which nearly every distribution includes.
- Windows 10 version 1803 or later, or Windows 11. These include `curl.exe`, `tar.exe` and `certutil`.
- An internet connection for the download and the first install.
- About 150 MB of free space for the manager and two Python versions.

You do not need Python already installed. Run everything as your ordinary user: the installer refuses to run as root on Linux and macOS, and refuses an administrator window on Windows.

## How the download works

Every release publishes two files: the release archive, named `osat-manager-python-<version>.tar.gz`, and `SHA256SUMS`, a one-line file holding the archive's checksum followed by its name. GitHub serves any file from the latest release at an address that contains the word `latest` instead of a version:

```text
https://github.com/steelcj/osat-manager-python/releases/latest/download/SHA256SUMS
```

So each set of commands below does four things: downloads `SHA256SUMS` from the latest release, reads the archive's name from it, downloads that archive from the latest release, and checks the archive against the checksum. If a new release happens to be published between the two downloads, the check fails safely and you simply start again.

We use these files rather than the "Source code" links on the release page. GitHub generates those on request and publishes no checksum for them.

## Linux and macOS

Open a terminal. The commands are the same on both systems except for the checksum step.

### Download the latest release

```sh
mkdir -p ~/Downloads/osat-manager-python-latest
cd ~/Downloads/osat-manager-python-latest
curl -fLO https://github.com/steelcj/osat-manager-python/releases/latest/download/SHA256SUMS
ARCHIVE=$(awk 'NR==1 {print $2}' SHA256SUMS)
echo "Latest release archive: $ARCHIVE"
curl -fLO "https://github.com/steelcj/osat-manager-python/releases/latest/download/$ARCHIVE"
```

The `echo` line shows which release you are about to install, for example `Latest release archive: osat-manager-python-1.0.2.tar.gz`.

### Check the download

On Linux:

```sh
sha256sum -c SHA256SUMS
```

On macOS:

```sh
shasum -a 256 -c SHA256SUMS
```

You should see the archive's name followed by `OK`. If you see `FAILED`, delete both files and download them again; if it happens again, stop and report it on the project's GitHub page.

### Unpack and install

```sh
tar -xzf "$ARCHIVE"
cd "${ARCHIVE%.tar.gz}"
./install.sh
```

The second line changes into the folder the archive unpacks to, which has the same name as the archive without `.tar.gz`, for example `osat-manager-python-1.0.2`.

The installer downloads a small temporary copy of Python, checks it, uses it once to run the manager, and deletes it afterwards. The manager then chooses the newest stable Python version, checks its download, installs it, installs itself, and writes the commands `python`, a versioned command such as `python3.14`, and `manage-python` into `~/.local/bin`. Lines starting with `[install.sh]` come from the installer and lines starting with `[manage-python]` come from the manager. The installer's last line says it is cleaning up the temporary Python.

### Make sure the commands are found

The commands live in `~/.local/bin`. If that folder is not yet on your PATH, the list of places your system looks for commands, the manager says so near the end of the install and tells you what to do:

- On Linux, most distributions add `~/.local/bin` automatically at login once the folder exists. Log out and back in, or run:
```sh
. ~/.profile
```
​       in the current terminal.
- On macOS, add this line to `~/.zshrc` and open a new terminal:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

If the manager printed no such message, the folder is already on your PATH.

### Check that it works

#### Check the path

```sh
command -v python
```

Output example:

```text
/home/initial/.local/bin/python
```

`command -v python` should print a path ending in `.local/bin/python`. 

#### Version check

```sh
python --version
```

Output example

```text
manage-python 1.0.2
```

#### manage-python --status

The manage python command is used to manage your Python installations

##### status

The status command tells about the status of any python installation the are managed using the manage-python command:

```sh
manage-python --status
```

Example output:

```text
manage-python 1.0.2

3.14
  aliases     python3.14  python
    default     3.14.7
```

`manage-python --status` output starts with the manager's version and lists each installed Python with the commands that run it, for example `python3.14` and `python` under 3.14. Continue with [After installing](#after-installing).

## Windows

This section is written for Command Prompt, with PowerShell versions of the commands that differ. The guide *Installing manage-python on Windows with Command Prompt* covers each step in more detail, including sample output.

### Open Command Prompt

Press the Windows key, type `cmd`, and choose **Command Prompt**. A prompt like `C:\Users\you>` is Command Prompt; `PS C:\Users\you>` is PowerShell. Open Command Prompt from the Start menu rather than by typing `cmd` inside PowerShell (see [If something goes wrong](#if-something-goes-wrong)).

### Download the latest release

```bat
cd /d "%USERPROFILE%\Downloads"
mkdir osat-manager-python-latest
cd osat-manager-python-latest
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/latest/download/SHA256SUMS
for /f "tokens=1,2" %a in (SHA256SUMS) do set "EXPECTED=%a"& set "ARCHIVE=%b"
echo Latest release archive: %ARCHIVE%
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/latest/download/%ARCHIVE%
```

The `for` line reads the checksum into `EXPECTED` and the archive's name into `ARCHIVE`. These commands are written for typing into Command Prompt; in a `.bat` file, write `%%a` and `%%b` in place of `%a` and `%b`.

In PowerShell:

```powershell
Set-Location "$env:USERPROFILE\Downloads"
New-Item -ItemType Directory -Force osat-manager-python-latest | Out-Null
Set-Location osat-manager-python-latest
curl.exe -fLO https://github.com/steelcj/osat-manager-python/releases/latest/download/SHA256SUMS
$expected, $archive = (Get-Content SHA256SUMS -TotalCount 1) -split '\s+'
"Latest release archive: $archive"
curl.exe -fLO "https://github.com/steelcj/osat-manager-python/releases/latest/download/$archive"
```

Write `curl.exe` in full in PowerShell: plain `curl` there is a different command with different options.

### Check the download

```bat
for /f "tokens=*" %h in ('certutil -hashfile %ARCHIVE% SHA256 ^| findstr /v ":"') do set "ACTUAL=%h"
if /i "%EXPECTED%"=="%ACTUAL%" (echo Checksum OK) else (echo Checksum MISMATCH, do not continue)
```

In PowerShell:

```powershell
$actual = (Get-FileHash $archive -Algorithm SHA256).Hash
if ($actual -eq $expected) { "Checksum OK" } else { "Checksum MISMATCH, do not continue" }
```

You should see `Checksum OK`. If you see `Checksum MISMATCH`, delete both files and download them again; if it happens again, stop and report it on the project's GitHub page.

### Unpack and install

```bat
tar -xzf %ARCHIVE%
cd %ARCHIVE:.tar.gz=%
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The second line changes into the folder the archive unpacks to, the archive's name without `.tar.gz`. In PowerShell, use these two lines in place of the first two; the install line is the same:

```powershell
tar -xzf $archive
Set-Location ($archive -replace '\.tar\.gz$', '')
```

The installer is a PowerShell script, and Windows often refuses to run PowerShell scripts by default. The install command asks PowerShell to run this one script without changing any settings <a name="apa-ms-execution-policies-citation"></a>([Microsoft, n.d.](#apa-ms-execution-policies-reference)).

As on Linux and macOS, the installer uses a temporary Python to run the manager, which installs the newest stable Python and itself. On Windows the manager writes its commands to `%LOCALAPPDATA%\Programs` and adds that folder to the start of your user PATH. It tells you it did so, where it saved a copy of your previous PATH, and how to undo the change.

### Open a new window and check that it works

Windows only gives the new PATH to windows opened after the change. Close this window, open a new Command Prompt, and run:

```bat
where.exe python
python --version
manage-python --status
```

`where.exe python` should list `%LOCALAPPDATA%\Programs\python.cmd` first. A `WindowsApps\python.exe` entry after it is a Microsoft Store shortcut; because the manager's folder comes first, `python` runs the installed Python.

## After installing

All of the manage-python commands from here on are the same on every system (Linux, MacOS and Windows).

### manage-python command

the cli help command

```sh
manage-python -h
```

Example output:

```text
manage-python
usage: manage-python [-h] [--install [SPEC] | --switch VERSION | --status | --remove VERSION | --alias OLD=NEW | --version] [--lang LANG]
```

### Adding another Python version

To add a second Python version alongside the first, for example 3.13 you would run:

```sh
manage-python --install 3.13
```

Output example:

```text
[manage-python] selected CPython 3.13.15+20260929 (x86_64-unknown-linux-gnu)
[manage-python] downloading SHA256SUMS for release 20260929...
[manage-python] downloading cpython-3.13.15+20260929-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz...
[manage-python] verified SHA-256
[manage-python] installing to ~/.local/share/python-manager/3.13.15...
[manage-python] alias written: ~/.local/bin/python
[manage-python] alias written: ~/.local/bin/python3.13
[manage-python] alias written: ~/.local/bin/python3.14
[manage-python] alias written: ~/.local/bin/manage-python
[manage-python] CPython 3.13.15 installed; python and python3.13 now run it
```

Notes about switching versions:

* The downloaded Python is automatically verified locally
* When you install a new Python version the python-manager automatically switches to the version of Python you just installed. You can confirm the new version is the active one using:

  ```sh
  python --version
  ```

  Expected output if you just installed version 3.13:

  ```text
  Python 3.13.15
  ```

### Switching Python versions

You can easily switch back and forth to different Python versions using the `manage-python` command. If you just installed `Python 3.13.15` and you want to switch to a different version you might follow a process something like this:

```sh
manage-python --status
```

Output if you followed the examples above showing that the python alias now uses Python version 3.13:

```text
manage-python 1.0.2

3.13
  aliases     python3.13  python
    default     3.13.15

3.14
  aliases     python3.14
    default     3.14.7
```

So your new alias for  `python` now runs Python 3.13 and you can confirm this by running:

```sh
python --version
```

Expected output if you just installed version 3.13

```text
Python 3.13.15
```

#### Switching versions command

Our status output shows us that the original Python 3.4.7 is still installed so we can switch back to it by running:

```sh
manage-python --switch 3.14.7
```

Output example:

```text
[manage-python] alias written: ~/.local/bin/python
[manage-python] alias written: ~/.local/bin/python3.14
[manage-python] python and python3.14 now run 3.14.7
```

We can see in the output that two aliases have been created for Python 3.14.7 meaning that either alias will output the same version:

```bash
python --version
python3.14 --version
```

Example of output of each command:

```text
Python 3.14.7
```

Switching versions is instant. Nothing is downloaded or removed, and every installed version stays available.

Now if you check the status of your managed Pythons you will see that it reflects the changes made by our `manage-python --switch` command:

```bash
manage-python --status
```

Output example:

```text
manage-python 1.0.2

3.13
  aliases     python3.13
    default     3.13.15

3.14
  aliases     python3.14  python
    default     3.14.7
```

### Creating Python virtual environments

You will want to Install packages into a virtual environment, and not into your installed Python(s).

#### Raw pip install

The manager protects each installed Python, so `pip install` into one of them is refused with a message pointing to virtual environments. <- THIS IS NOT CURRENTLY TRUE, running `pip install test`gives the following output:

```text
Command 'pip' not found, but can be installed with:
sudo apt install python3-pip
```

#### Creating a venv

 On Linux and macOS:

```sh
mkdir ~/.venvs
cd ~/.venvs
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install requests
```

On linux `which python` will now point to the Python venv we just created.

```text
/home/initial/.venvs/.venv/bin/python
```

On Windows, activate with `.venv\Scripts\activate` instead.

## Installation cleanup

### Linux

The downloaded release files are no longer needed once the install finishes. You can delete the `osat-manager-python-latest` folder in your Downloads.

```bash
rm -R ~/Downloads/osat-manager-python-latest
```

## Installing a specific release instead

To install a particular release rather than the latest, replace `latest/download` with `download/v<version>` in both download addresses, for example:

```text
https://github.com/steelcj/osat-manager-python/releases/download/v1.0.2/SHA256SUMS
```

Everything else stays the same.

## If something goes wrong

**The first download fails with a 404 error.** Check the address for typing mistakes. If it is correct, the project may have no published release at the moment; see its releases page on GitHub.

**`python` or `manage-python` is not found after the install.** On Linux and macOS, follow [Make sure the commands are found](#make-sure-the-commands-are-found). On Windows, open a new Command Prompt window.

**`python3` runs a different Python, or opens the Microsoft Store on Windows.** This is expected. The manager does not create a `python3` command; use `python` or a versioned command such as `python3.14`.

**The installer stops with "refusing to run as root".** Run it again as your ordinary user, without `sudo`. On Windows, the equivalent is an administrator window; open an ordinary one.

**On Windows, the installer stops with "Get-FileHash is not recognized".** This affects release 1.0.2 when Command Prompt was started from inside a PowerShell 7 window. Open a fresh Command Prompt from the Start menu and run the install command again, or clear the inherited setting in the same window first:

```bat
set "PSModulePath="
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Releases after 1.0.2 compute the checksum without `Get-FileHash`, so this no longer happens.

**Undoing the Windows PATH change.** Run `rundll32 sysdm.cpl,EditEnvironmentVariables`, select Path under your user variables, and remove the `%LOCALAPPDATA%\Programs` entry. The PATH you had before is saved in `%LOCALAPPDATA%\python-manager\logs\`.

## License

This document, *Installing manage-python from the Latest Release*, by **Christopher Steel**, with AI assistance from **Claude Opus 5.5 (Anthropic)**, is licensed under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).

## Resources

### osat-manager-python

- [Proposal: osat-manager-python Layout, Lifecycle and Aliases](#apa-omp-proposal-reference)
- [Installing manage-python on Windows with Command Prompt](installing-manage-python-on-windows-with-command-prompt-v0-1-2.md)

### GitHub

- [Linking to releases](#apa-gh-linking-releases-reference)

### Windows

- [about_Execution_Policies](#apa-ms-execution-policies-reference)

## References

<a name="apa-gh-linking-releases-reference"></a>GitHub. (n.d.). *Linking to releases*. GitHub Docs. https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases
[Return to citation](#apa-gh-linking-releases-citation)

<a name="apa-ms-execution-policies-reference"></a>Microsoft. (n.d.). *about_Execution_Policies*. Microsoft Learn. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
[Return to citation](#apa-ms-execution-policies-citation)

<a name="apa-omp-proposal-reference"></a>Steel, C. (2026). *Proposal: osat-manager-python layout, lifecycle and aliases* (Version 0.7.0). GitHub. https://github.com/steelcj/osat-manager-python
[Return to citation](#apa-omp-proposal-citation)

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.1.0 | Draft | Initial guide covering Linux, macOS and Windows, written against release 1.0.2, with download commands that follow the latest release rather than a fixed version |
