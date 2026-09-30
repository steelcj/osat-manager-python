#Requires -Version 5.1
# validate-windows.ps1
#
# source
#   project: osat-manager-python
#   path: validate-windows.ps1
#
# Hardware validation of manage-python on Windows 11, run from a fresh VM
# snapshot under Windows PowerShell 5.1. The counterpart of
# validate-windows.py in osat-fluent-restic-tool, which simulates Windows on
# another platform: this script runs the real thing, so it covers what a
# simulation cannot: install.ps1, the registry write, the .cmd and .ps1
# aliases under cmd.exe and powershell.exe, command precedence, and the
# lifecycle against real python-build-standalone downloads.
#
# It changes the account it runs under: it installs runtimes, writes aliases
# and prepends %LOCALAPPDATA%\Programs to the user PATH. Run it only on a
# disposable VM snapshot, and revert the snapshot afterwards.
#
# Every check prints PASS or FAIL; facts worth reporting print NOTE. The
# report file, validate-windows-report-<computer>-<UTC>.txt, collects all of
# it together with the captured output and a checklist of manual steps.
#
# Usage, from the extracted release folder with this script copied into it:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-windows.ps1 -FreshSnapshot
#
# See en/docs/guides/development/windows-validation-for-manage-python-v0-3-0.md.

param(
    [switch]$FreshSnapshot,
    [string]$ReportDir = $PSScriptRoot,
    [string]$Line = "3.12",
    [string]$Other = "3.13"
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$Started = [DateTime]::UtcNow
$Stamp = $Started.ToString("yyyyMMdd'T'HHmmss'Z'")
$Work = Join-Path $env:TEMP "manage-python-validate-$Stamp"
$Programs = Join-Path $env:LOCALAPPDATA "Programs"
$Share = Join-Path $env:LOCALAPPDATA "python-manager"
$Logs = Join-Path $Share "logs"
$OperatorDir = Join-Path $env:APPDATA "python-manager"
$ReportPath = Join-Path $ReportDir "validate-windows-report-$($env:COMPUTERNAME)-$Stamp.txt"
$Report = New-Object System.Collections.Generic.List[string]
$Failures = New-Object System.Collections.Generic.List[string]
$Captured = New-Object System.Collections.Generic.List[string]
$script:ChildPath = $env:Path

# -- Reporting -----------------------------------------------------------------

function Say([string]$Text) {
    Write-Host $Text
    $Report.Add($Text)
}

function Section([string]$Title) {
    Say ""
    Say "[$Title]"
}

function Indent([string]$Text) {
    return "        " + (($Text.TrimEnd() -replace "`r", "") -replace "`n", "`n        ")
}

function Check([string]$Name, [bool]$Condition, [string]$Detail = "") {
    if ($Condition) {
        Say "  PASS  $Name"
    } else {
        Say "  FAIL  $Name"
        if ($Detail) { Say (Indent $Detail) }
        $Failures.Add($Name)
    }
}

function Note([string]$Name, [string]$Value) {
    Say "  NOTE  ${Name}:"
    Say (Indent $Value)
}

function Capture([string]$Title, [string]$Text) {
    $Captured.Add("=== $Title")
    $Captured.Add(($Text -replace "`r", "").TrimEnd())
    $Captured.Add("")
}

# -- Running things ------------------------------------------------------------

function Write-Text([string]$Path, [string]$Text, [switch]$Crlf) {
    if ($Crlf) { $Text = ($Text -replace "`r", "") -replace "`n", "`r`n" }
    [IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding $false))
}

# Start a process with its own output captured, bypassing PowerShell's
# handling of native standard error. Path is the "new terminal" PATH once
# the manager has changed it.
function Invoke-Native([string]$File, [string]$Arguments, [hashtable]$Env = @{}, [int]$Seconds = 900) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $File
    $info.Arguments = $Arguments
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.WorkingDirectory = $Work
    $info.EnvironmentVariables["Path"] = $script:ChildPath
    foreach ($key in $Env.Keys) {
        if ($null -eq $Env[$key]) { $info.EnvironmentVariables.Remove($key) }
        else { $info.EnvironmentVariables[$key] = [string]$Env[$key] }
    }
    $process = [System.Diagnostics.Process]::Start($info)
    $out = $process.StandardOutput.ReadToEndAsync()
    $err = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($Seconds * 1000)) {
        $process.Kill()
        return [pscustomobject]@{ Code = -1; Out = $out.Result; Err = "timed out after $Seconds s`n" + $err.Result }
    }
    $process.WaitForExit()
    return [pscustomobject]@{ Code = $process.ExitCode; Out = $out.Result; Err = $err.Result }
}

$script:BatchCount = 0

# Run a batch file under cmd.exe; the body follows "@echo off".
function Invoke-Cmd([string]$Body, [hashtable]$Env = @{}, [int]$Seconds = 900) {
    $script:BatchCount++
    $bat = Join-Path $Work ("step{0:D2}.bat" -f $script:BatchCount)
    Write-Text $bat ("@echo off`n" + $Body + "`n") -Crlf
    return Invoke-Native "cmd.exe" "/d /s /c `"`"$bat`"`"" $Env $Seconds
}

$script:PsCount = 0

# Run a script under Windows PowerShell 5.1 with a bypassed execution policy.
function Invoke-Ps([string]$Body, [hashtable]$Env = @{}, [int]$Seconds = 900) {
    $script:PsCount++
    $ps1 = Join-Path $Work ("step{0:D2}.ps1" -f $script:PsCount)
    Write-Text $ps1 $Body -Crlf
    return Invoke-Native "powershell.exe" "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$ps1`"" $Env $Seconds
}

function Show($Result) {
    return "exit $($Result.Code)`nstdout:`n$($Result.Out)`nstderr:`n$($Result.Err)"
}

# -- Facts about the machine ---------------------------------------------------

function Get-UserPath {
    $key = Get-Item "HKCU:\Environment"
    if ($key.GetValueNames() -notcontains "Path") { return [pscustomobject]@{ Kind = "absent"; Raw = $null } }
    $kind = $key.GetValueKind("Path").ToString()
    $name = switch ($kind) { "ExpandString" { "REG_EXPAND_SZ" } "String" { "REG_SZ" } default { $kind } }
    return [pscustomobject]@{ Kind = $name; Raw = $key.GetValue("Path", $null, "DoNotExpandEnvironmentNames") }
}

# PATH as a terminal opened after the change sees it: machine, then user.
function Get-NewTerminalPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    return ($machine.TrimEnd(";") + ";" + $user)
}

function Get-Pointer {
    $values = @{}
    $file = Join-Path $Share "python-manager.env.cmd"
    if (Test-Path $file) {
        foreach ($text in (Get-Content $file)) {
            if ($text -match '^set "(PYTHON_MANAGER_[A-Z0-9_]+)=([^"]*)"$') { $values[$Matches[1]] = $Matches[2] }
        }
    }
    return $values
}

# The version an alias runs, through its .cmd under cmd.exe.
function Get-CmdVersion([string]$Alias) {
    $result = Invoke-Cmd "call `"%LOCALAPPDATA%\Programs\$Alias.cmd`" --version"
    if ($result.Out -match "Python (\d+\.\d+\.\d+)") { return $Matches[1] }
    return "none: " + (Show $result)
}

# Run PowerShell code as a user's session runs it: the machine's default
# execution policy (this script's -ExecutionPolicy Bypass is not passed on:
# it travels in PSExecutionPolicyPreference, which is removed), no profile,
# and the code passed as an encoded command, which even the Restricted
# policy allows. $Exe is powershell.exe or pwsh.exe. OSAT_WORK names the
# work directory, so no path is quoted into the code.
function Invoke-PsDefault([string]$Exe, [string]$Body, [hashtable]$Env = @{}, [int]$Seconds = 900) {
    $vars = @{ PSExecutionPolicyPreference = $null; OSAT_WORK = $Work }
    foreach ($key in $Env.Keys) { $vars[$key] = $Env[$key] }
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Body))
    return Invoke-Native $Exe "-NoProfile -NonInteractive -EncodedCommand $encoded" $vars $Seconds
}

# The version an alias runs when a PowerShell session calls it by name.
function Get-PsVersion([string]$Exe, [string]$Alias) {
    $result = Invoke-PsDefault $Exe "$Alias --version; exit `$LASTEXITCODE"
    if ($result.Out -match "Python (\d+\.\d+\.\d+)") { return $Matches[1] }
    return "none: " + (Show $result)
}

function Manage([string]$Arguments, [hashtable]$Env = @{}) {
    return Invoke-Cmd "call `"%LOCALAPPDATA%\Programs\manage-python.cmd`" $Arguments" $Env 1800
}

function Log-Lines {
    $file = Join-Path $Logs "manage-python.log"
    if (Test-Path $file) { return @(Get-Content $file) }
    return @()
}

# -- Preconditions -------------------------------------------------------------

$problems = @()
if ($PSVersionTable.PSEdition -ne "Desktop" -or $PSVersionTable.PSVersion.Major -ne 5) {
    $problems += "run this under Windows PowerShell 5.1 (powershell.exe), not PowerShell $($PSVersionTable.PSVersion)"
}
if (-not $FreshSnapshot) {
    $problems += "this script changes the account it runs under; run it on a fresh VM snapshot and pass -FreshSnapshot"
}
if (Test-Path $Share) {
    $problems += "$Share already exists; start from a fresh snapshot"
}
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $problems += "run as an ordinary user, not from an elevated (Administrator) window"
}
foreach ($required in @("install.ps1", "manage-python.py", "VERSION")) {
    if (-not (Test-Path (Join-Path $Root $required))) { $problems += "$required is not next to this script in $Root" }
}
if ($problems.Count -gt 0) {
    foreach ($problem in $problems) { Write-Host "[validate-windows] refusing: $problem" }
    exit 2
}
New-Item -ItemType Directory -Path $Work | Out-Null
$Shells = @(@{ Name = "Windows PowerShell 5.1"; Exe = "powershell.exe" })
$PwshCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue
if ($null -ne $PwshCommand) { $Shells += @{ Name = "PowerShell 7"; Exe = $PwshCommand.Source } }

try {
    $Version = (Get-Content (Join-Path $Root "VERSION") -TotalCount 1).Trim()
    # The registry rather than Get-CimInstance: CimCmdlets is loaded through
    # PSModulePath, which may be PowerShell 7's (see section 11).
    $os = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    Say "manage-python Windows validation"
    Say "  manager under test: $Version, from $Root"
    Say "  started:            $($Started.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
    # ProductName still says Windows 10 on Windows 11; build 22000 and later is Windows 11.
    Say "  machine:            $($os.ProductName) $($os.DisplayVersion) build $($os.CurrentBuild).$($os.UBR), $env:PROCESSOR_ARCHITECTURE"
    Say "  PowerShell:         $($PSVersionTable.PSVersion) ($($PSVersionTable.PSEdition))"
    Say "  culture:            $((Get-Culture).Name), UI $((Get-UICulture).Name)"
    Say "  work directory:     $Work"

    # -- [1] Before ----------------------------------------------------------------
    Section "1 Before installing"
    $before = Get-UserPath
    Note "user Path type" $before.Kind
    Note "user Path value" ([string]$before.Raw)
    Note "execution policies" ((Get-ExecutionPolicy -List | Out-String).Trim())
    $storeAlias = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\python.exe"
    Note "Microsoft Store python alias present" ([string](Test-Path $storeAlias))
    $pre = Invoke-Ps "Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object { `$_.Source }"
    Note "Get-Command python -All" ($(if ($pre.Out.Trim()) { $pre.Out.Trim() } else { "(none)" }))

    # -- [2] Bootstrap -------------------------------------------------------------
    Section "2 Bootstrap through install.ps1 under Windows PowerShell 5.1"
    $boot = Invoke-Native "powershell.exe" "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$(Join-Path $Root 'install.ps1')`" --install $Line" @{} 1800
    Capture "install.ps1 --install $Line" (Show $boot)
    Check "install.ps1 exits 0" ($boot.Code -eq 0) (Show $boot)
    $pointer = Get-Pointer
    $newest = [string]$pointer["PYTHON_MANAGER_DEFAULT"]
    Check "a $Line runtime is the default" ($newest.StartsWith("$Line.")) ("pointer: " + ($pointer | Out-String))
    Check "the manager installed itself" (Test-Path (Join-Path $Share "manage-python\$Version\manage-python.py"))
    Check "SELF is $Version" ($pointer["PYTHON_MANAGER_SELF"] -eq $Version)
    foreach ($name in @("python", "python$Line", "manage-python")) {
        Check "alias $name.cmd written" (Test-Path (Join-Path $Programs "$name.cmd"))
        Check "no $name.ps1 written" (-not (Test-Path (Join-Path $Programs "$name.ps1")))
    }
    Check "only the .cmd pointer is written" ((Test-Path (Join-Path $Share "python-manager.env.cmd")) -and -not (Test-Path (Join-Path $Share "python-manager.env.ps1")))
    Check "no bootstrap Python left in TEMP" (@(Get-ChildItem $env:TEMP -Filter "osat-manager-python-bootstrap-*" -ErrorAction SilentlyContinue).Count -eq 0)

    # -- [3] The user PATH write ---------------------------------------------------
    Section "3 The user PATH write"
    $after = Get-UserPath
    Note "user Path after" ("$($after.Kind): $($after.Raw)")
    $expectedKind = if ($before.Kind -eq "absent") { "REG_EXPAND_SZ" } else { $before.Kind }
    Check "registry type kept ($expectedKind)" ($after.Kind -eq $expectedKind) "was $($before.Kind), now $($after.Kind)"
    $entry = if ($expectedKind -eq "REG_SZ") { "$env:LOCALAPPDATA\Programs" } else { "%LOCALAPPDATA%\Programs" }
    Check "Path starts with $entry" (([string]$after.Raw).StartsWith($entry)) ([string]$after.Raw)
    $announce = "[manage-python] Added %LOCALAPPDATA%\Programs to the start of your user PATH (HKCU\Environment\Path) so the manager's commands are found. Open a new terminal to use them."
    Check "the change is announced" ($boot.Err.Contains($announce)) $boot.Err
    Check "the undo instructions are shown" ($boot.Err -match "\[manage-python\] Your previous PATH was saved to %LOCALAPPDATA%\\python-manager\\logs\\path-backup-\d{8}T\d{6}Z\.txt\. To undo, run: rundll32 sysdm\.cpl,EditEnvironmentVariables  then select Path under your user variables and remove that entry\.") $boot.Err
    $backups = @(Get-ChildItem $Logs -Filter "path-backup-*.txt" -ErrorAction SilentlyContinue)
    Check "one backup file" ($backups.Count -eq 1) (($backups | ForEach-Object { $_.Name }) -join ", ")
    if ($backups.Count -ge 1) {
        $backupLines = @(Get-Content $backups[0].FullName)
        Capture "PATH backup $($backups[0].Name)" ($backupLines -join "`n")
        Check "backup records the previous type" ($backupLines -contains "type: $($before.Kind)") ($backupLines -join "`n")
        Check "backup records the previous value" ($backupLines -contains ("value: " + [string]$before.Raw)) ($backupLines -join "`n")
        Check "backup has CRLF line endings" ([IO.File]::ReadAllText($backups[0].FullName).Contains("`r`n"))
    }
    $pathLines = @(Log-Lines | Where-Object { $_ -match "^\S+ path " })
    Check "one path log line" ($pathLines.Count -eq 1) ((Log-Lines) -join "`n")
    Check "path log line format" ($pathLines.Count -ge 1 -and $pathLines[0] -match '^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ path %LOCALAPPDATA%\\Programs ok: prepended to user PATH, backup %LOCALAPPDATA%\\python-manager\\logs\\path-backup-\d{8}T\d{6}Z\.txt$') ($pathLines -join "`n")

    $script:ChildPath = Get-NewTerminalPath
    $order = Invoke-Ps "Get-Command python -All | ForEach-Object { `$_.Source }"
    $sources = @($order.Out -split "`r?`n" | Where-Object { $_ })
    Note "a new terminal: Get-Command python -All" ($sources -join "`n")
    Check "a new terminal finds the manager's python first" ($sources.Count -ge 1 -and $sources[0] -like "$Programs\*") ($sources -join "`n")
    $storeIndex = [array]::FindIndex([string[]]$sources, [Predicate[string]]{ param($s) $s -like "*\WindowsApps\python.exe" })
    if ($storeIndex -ge 0) { Check "the Store alias comes after it" ($storeIndex -gt 0) ($sources -join "`n") }
    else { Note "the Store alias" "not on PATH in a new terminal" }
    $where = Invoke-Cmd "where python"
    Note "a new terminal: where python" $where.Out.Trim()
    Check "cmd.exe finds python.cmd first" (($where.Out -split "`r?`n")[0] -eq (Join-Path $Programs "python.cmd")) $where.Out

    # -- [4] More installs through the installed manager ---------------------------
    Section "4 More installs through the installed manager"
    $third = Manage "--install $Other"
    Capture "manage-python.cmd --install $Other" (Show $third)
    Check "manage-python.cmd --install $Other exits 0" ($third.Code -eq 0) (Show $third)
    $pointer = Get-Pointer
    $otherVersion = [string]$pointer["PYTHON_MANAGER_" + $Other.Replace(".", "_")]
    Check "python now runs $otherVersion" ((Get-CmdVersion "python") -eq $otherVersion)
    Check "python$Line still runs $newest" ((Get-CmdVersion "python$Line") -eq $newest)
    Check "an unchanged PATH is not announced" (-not $third.Err.Contains("Added %LOCALAPPDATA%")) $third.Err
    Check "an unchanged PATH is not backed up again" (@(Get-ChildItem $Logs -Filter "path-backup-*.txt").Count -eq 1)
    Check "an unchanged PATH is not logged again" (@(Log-Lines | Where-Object { $_ -match "^\S+ path " }).Count -eq 1)

    $parts = $newest.Split(".")
    $older = "{0}.{1}.{2}" -f $parts[0], $parts[1], ([int]$parts[2] - 1)
    $fourth = Invoke-PsDefault "powershell.exe" "manage-python --install $older; exit `$LASTEXITCODE" @{} 1800
    Capture "manage-python --install $older from Windows PowerShell 5.1" (Show $fourth)
    Check "manage-python --install $older from Windows PowerShell 5.1 (default policy) exits 0" ($fourth.Code -eq 0) (Show $fourth)
    Check "python and python$Line run $older" ((Get-CmdVersion "python") -eq $older -and (Get-PsVersion "powershell.exe" "python$Line") -eq $older)

    # -- [5] Aliases: arguments, exit codes, environment ---------------------------
    Section "5 The .cmd aliases from cmd.exe and from PowerShell"
    Write-Text (Join-Path $Work "args.py") "import json, os, sys`nprint(json.dumps({'argv': sys.argv[1:], 'keep': os.environ.get('OSAT_KEEP')}))`n"
    Write-Text (Join-Path $Work "exitcode.py") "import sys`nsys.exit(int(sys.argv[1]))`n"
    New-Item -ItemType Directory -Path $OperatorDir -Force | Out-Null
    Write-Text (Join-Path $OperatorDir "env.cmd") "set `"OSAT_KEEP=changed-by-operator`"`n" -Crlf
    $expectedArgs = '{"argv": ["a b", "c", "d=e", "f,g"], "keep": "changed-by-operator"}'

    $cmdRun = Invoke-Cmd @"
set "OSAT_KEEP=before"
call "%LOCALAPPDATA%\Programs\python$Line.cmd" "%~dp0args.py" "a b" c d=e f,g
echo EXIT0=%ERRORLEVEL%
call "%LOCALAPPDATA%\Programs\python$Line.cmd" "%~dp0exitcode.py" 7
echo EXIT7=%ERRORLEVEL%
echo KEEP=%OSAT_KEEP%
if defined PYTHON_MANAGER_DEFAULT (echo LEAK=yes) else (echo LEAK=no)
"@
    Capture "python$Line.cmd under cmd.exe" (Show $cmdRun)
    $cmdOut = @($cmdRun.Out -split "`r?`n")
    Check "cmd.exe: arguments pass through" ($cmdOut -contains $expectedArgs) (Show $cmdRun)
    Check "cmd.exe: exit code 0" ($cmdOut -contains "EXIT0=0") (Show $cmdRun)
    Check "cmd.exe: exit code 7" ($cmdOut -contains "EXIT7=7") (Show $cmdRun)
    Check "cmd.exe: the operator env.cmd is read, then setlocal restores the caller's value" ($cmdOut -contains "KEEP=before") (Show $cmdRun)
    Check "cmd.exe: no pointer variables left behind" ($cmdOut -contains "LEAK=no") (Show $cmdRun)

    $psBody = @"
`$env:OSAT_KEEP = 'before'
function Snap { (Get-ChildItem Env: | Sort-Object Name | ForEach-Object { "`$(`$_.Name)=`$(`$_.Value)" }) -join "``n" }
`$before = Snap
python$Line (Join-Path `$env:OSAT_WORK 'args.py') 'a b' c 'd=e' 'f,g'
"EXIT0=`$LASTEXITCODE"
python$Line (Join-Path `$env:OSAT_WORK 'exitcode.py') 7
"EXIT7=`$LASTEXITCODE"
if (`$before -ceq (Snap)) { 'ENV=unchanged' } else { 'ENV=changed' }
python$Line (Join-Path `$env:OSAT_WORK 'args.py') '100%' 'a^b' '%OSAT_KEEP%' '!x!'
"@
    foreach ($shell in $Shells) {
        $psRun = Invoke-PsDefault $shell.Exe $psBody
        Capture "python$Line.cmd from $($shell.Name)" (Show $psRun)
        $psOut = @($psRun.Out -split "`r?`n")
        Check "$($shell.Name): arguments pass through the .cmd" ($psOut -contains $expectedArgs) (Show $psRun)
        Check "$($shell.Name): `$LASTEXITCODE 0 through the .cmd" ($psOut -contains "EXIT0=0") (Show $psRun)
        Check "$($shell.Name): `$LASTEXITCODE 7 through the .cmd" ($psOut -contains "EXIT7=7") (Show $psRun)
        Check "$($shell.Name): the session environment is unchanged" ($psOut -contains "ENV=unchanged") (Show $psRun)
        Note "$($shell.Name): what python receives for 100%, a^b, %OSAT_KEEP% and !x!" ([string]($psOut | Select-Object -Last 1))
    }

    $key = "PYTHON_MANAGER_" + $Line.Replace(".", "_")
    Write-Text (Join-Path $OperatorDir "env.cmd") "set `"$key=`"`n" -Crlf
    $unsetCmd = Invoke-Cmd "call `"%LOCALAPPDATA%\Programs\python$Line.cmd`" --version`necho EXIT=%ERRORLEVEL%"
    Capture "python$Line.cmd with $key unset, from cmd.exe" (Show $unsetCmd)
    Check "cmd.exe: with the key unset the alias exits 1" (@($unsetCmd.Out -split "`r?`n") -contains "EXIT=1") (Show $unsetCmd)
    Check "cmd.exe: with the key unset the alias says so" ($unsetCmd.Err.Contains("$key is not set")) (Show $unsetCmd)
    foreach ($shell in $Shells) {
        $unsetPs = Invoke-PsDefault $shell.Exe "python$Line --version; `"EXIT=`$LASTEXITCODE`""
        Capture "python$Line with $key unset, from $($shell.Name)" (Show $unsetPs)
        Check "$($shell.Name): with the key unset the alias exits 1 and says so" ((@($unsetPs.Out -split "`r?`n") -contains "EXIT=1") -and ($unsetPs.Out + $unsetPs.Err).Contains("$key is not set")) (Show $unsetPs)
    }
    Remove-Item (Join-Path $OperatorDir "env.cmd")

    # -- [6] Which file each shell runs -------------------------------------
    Section "6 Which file each shell runs, under the default execution policy"
    foreach ($shell in $Shells) {
        $which = Invoke-PsDefault $shell.Exe "'policy: ' + (Get-ExecutionPolicy); Get-Command python$Line -All | ForEach-Object { `"`$(`$_.CommandType) `$(`$_.Source)`" }; python$Line --version; exit `$LASTEXITCODE"
        Capture "python$Line from $($shell.Name)" (Show $which)
        Note "$($shell.Name)" ((Show $which).Trim())
        Check "$($shell.Name) finds no .ps1 for python$Line" (-not ($which.Out -match "ExternalScript")) (Show $which)
        Check "python$Line runs in $($shell.Name) with the default execution policy" ($which.Code -eq 0 -and $which.Out -match "Python $older") (Show $which)
    }
    $bare = Invoke-Cmd "python$Line --version"
    Check "cmd.exe runs python$Line by its bare name" ($bare.Out -match "Python $older") (Show $bare)

    # -- [7] A batch file without call ---------------------------------------------
    Section "7 A batch file calling python$Line without call"
    $noCall = Invoke-Cmd "python$Line `"%~dp0exitcode.py`" 3`necho CONTINUED"
    Capture "without call" (Show $noCall)
    Note "without call" ("continues after python: " + ($noCall.Out -match "CONTINUED") + "; exit code " + $noCall.Code)
    $withCall = Invoke-Cmd "call python$Line `"%~dp0exitcode.py`" 3`necho CONTINUED %ERRORLEVEL%"
    Check "with call, the batch file continues and sees exit code 3" ($withCall.Out -match "CONTINUED 3") (Show $withCall)

    # -- [8] pip and venv ----------------------------------------------------------
    Section "8 pip refuses the runtime; a venv works"
    $offlinePip = @{ PIP_NO_INDEX = "1" }
    $pip = Invoke-Cmd "call `"%LOCALAPPDATA%\Programs\python$Line.cmd`" -m pip install --dry-run six" $offlinePip
    Capture "pip install into the runtime" (Show $pip)
    Check "pip refuses to install into the runtime" ($pip.Code -ne 0 -and ($pip.Out + $pip.Err).Contains("externally-managed-environment")) (Show $pip)
    $pipLines = @(($pip.Out + $pip.Err) -split "`r?`n" | ForEach-Object { $_.Trim() })
    Check "pip's message names python$Line -m venv .venv on a line of its own" ($pipLines -contains "python$Line -m venv .venv") (Show $pip)
    Check "pip's message has no stray '.' line" (-not ($pipLines -contains ".")) (Show $pip)
    $venv = Join-Path $Work "venv"
    $made = Invoke-Cmd "call `"%LOCALAPPDATA%\Programs\python$Line.cmd`" -m venv `"$venv`""
    Check "python$Line -m venv works" ($made.Code -eq 0) (Show $made)
    $venvPython = Join-Path $venv "Scripts\python.exe"
    $venvVersion = Invoke-Native $venvPython "--version"
    Check "the venv runs $older" ($venvVersion.Out -match "Python $older") (Show $venvVersion)
    $venvPip = Invoke-Native $venvPython "-m pip install --dry-run six" $offlinePip
    Check "pip in the venv is not refused as externally managed" (-not ($venvPip.Out + $venvPip.Err).Contains("externally-managed-environment")) (Show $venvPip)

    # -- [9] Switch, rename, remove, offline restore -------------------------------
    Section "9 Switch, rename, remove and restore offline"
    $r = Manage "--switch $newest"
    Check "--switch $newest" ($r.Code -eq 0) (Show $r)
    Check "python runs $newest" ((Get-CmdVersion "python") -eq $newest)
    Check "python$Other still runs $otherVersion" ((Get-CmdVersion "python$Other") -eq $otherVersion)
    $r = Manage "--alias python$Line=py312"
    Check "--alias python$Line=py312" ($r.Code -eq 0) (Show $r)
    Check "py312.cmd written, and no py312.ps1" ((Test-Path (Join-Path $Programs "py312.cmd")) -and -not (Test-Path (Join-Path $Programs "py312.ps1")))
    Check "python$Line.cmd removed" (-not (Test-Path (Join-Path $Programs "python$Line.cmd")))
    Check "py312 runs $newest from cmd.exe and Windows PowerShell 5.1" ((Get-CmdVersion "py312") -eq $newest -and (Get-PsVersion "powershell.exe" "py312") -eq $newest)
    $r = Manage "--switch $older"
    Check "py312 follows a switch" ($r.Code -eq 0 -and (Get-CmdVersion "py312") -eq $older) (Show $r)
    $r = Manage "--install $newest"
    Check "py312 follows an install and keeps its name" ($r.Code -eq 0 -and (Get-CmdVersion "py312") -eq $newest -and -not (Test-Path (Join-Path $Programs "python$Line.cmd"))) (Show $r)
    $status = Manage "--status"
    Capture "--status" (Show $status)
    $statusLines = @($status.Out -split "`r?`n")
    Check "--status starts with manage-python $Version" ($statusLines[0] -eq "manage-python $Version") $status.Out
    Check "--status shows the rename" ($status.Out.Contains("  aliases     py312  python")) $status.Out
    $r = Manage "--remove $newest"
    Check "--remove refuses the default" ($r.Code -eq 1) (Show $r)
    $r = Manage "--remove $older"
    Check "--remove $older" ($r.Code -eq 0 -and -not (Test-Path (Join-Path $Share $older))) (Show $r)
    Check "--status lists $older as archived" ((Manage "--status").Out -match "archived    $([regex]::Escape($older))\+") ""
    # Windows environment names ignore case, so these also cover https_proxy and http_proxy.
    $dead = @{ HTTPS_PROXY = "http://127.0.0.1:9"; HTTP_PROXY = "http://127.0.0.1:9" }
    $r = Manage "--install $older" $dead
    Capture "offline restore of $older" (Show $r)
    Check "--install $older with the network unreachable" ($r.Code -eq 0) (Show $r)
    $provenance = Join-Path $Share "$older\PROVENANCE"
    Check "restored from the local archive" ((Test-Path $provenance) -and ((Get-Content $provenance) -match "^source: local archive \(")) ""
    Check "the restored runtime runs" ((Get-CmdVersion "python") -eq $older)
    Check "the restored runtime is protected" (Test-Path (Join-Path $Share "$older\python\Lib\EXTERNALLY-MANAGED"))

    # -- [10] The operator log -----------------------------------------------------
    Section "10 The operator log"
    $log = @(Log-Lines)
    Capture "manage-python.log" ($log -join "`n")
    $actions = @($log | ForEach-Object { ($_ -split " ")[1] })
    Check "log actions in order" (($actions -join " ") -eq "path install install install switch alias switch install remove remove install") ($log -join "`n")
    $failed = @($log | Where-Object { $_ -match " failed: " })
    Check "only the refused remove failed" ($failed.Count -eq 1 -and $failed[0] -match " remove $([regex]::Escape($newest)) failed: ") ($log -join "`n")

    # -- [11] install.ps1 from a Command Prompt opened inside PowerShell 7 ----
    # Windows PowerShell 5.1 started this way inherits PowerShell 7's
    # PSModulePath and cannot load script-defined cmdlets such as Get-FileHash.
    Section "11 install.ps1 from a Command Prompt opened inside PowerShell 7"
    $pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if ($null -eq $pwsh) {
        Note "PowerShell 7" "pwsh.exe is not installed; do manual step M6 instead"
    } else {
        $repro = Join-Path $Work "from-pwsh.bat"
        Write-Text $repro @"
@echo off
powershell.exe -NoProfile -Command "`$env:PSModulePath"
echo ---
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(Join-Path $Root 'install.ps1')" --install $older
echo EXIT=%ERRORLEVEL%
"@ -Crlf
        # PowerShell 7 as the Start menu starts it: with the machine's
        # PSModulePath, which it then extends for everything it runs.
        $machineModules = [Environment]::GetEnvironmentVariable("PSModulePath", "Machine")
        $nested = Invoke-Native $pwsh.Source "-NoProfile -NonInteractive -Command `"& cmd.exe /d /c '$repro'`"" @{ PSModulePath = $machineModules } 1800
        Capture "PowerShell 7 > cmd.exe > powershell.exe 5.1 > install.ps1" (Show $nested)
        $seen = ($nested.Out -split "---")[0].Trim()
        Note "PSModulePath seen by Windows PowerShell 5.1" $seen
        # PowerShell 7's paths end in \PowerShell\Modules (user and Program
        # Files), \PowerShell\7\Modules, or, for the Store install,
        # \microsoft.powershell_<version>...\Modules; Windows PowerShell's
        # end in \WindowsPowerShell\...\Modules and do not match.
        $ps7Pattern = '(?i)(\\PowerShell\\(7[^\\]*\\)?Modules|\\microsoft\.powershell_[^\\]*\\Modules)\\?$'
        $ps7Entries = @($seen -split ";" | Where-Object { $_ -match $ps7Pattern })
        Note "PowerShell 7 module paths inherited" ($(if ($ps7Entries.Count -gt 0) { $ps7Entries -join "`n" } else { "none" }))
        Check "the scenario is reproduced: Windows PowerShell 5.1 sees PowerShell 7's module paths" ($ps7Entries.Count -gt 0) $seen
        Check "install.ps1 exits 0 from cmd.exe inside PowerShell 7" ($nested.Out -match "EXIT=0") (Show $nested)
        Check "no cmdlet is missing" (-not ($nested.Out + $nested.Err).Contains("is not recognized")) (Show $nested)
        Check "the bootstrap checksum is verified and extraction follows" ($nested.Out -match "verifying checksum" -and $nested.Out -match "extracting") (Show $nested)
    }

    # -- [12] Every alias from every shell ------------------------------------
    Section "12 python, a minor line and manage-python from every shell"
    $cmdMatrix = Invoke-Cmd "call python --version`ncall python$Other --version`ncall manage-python --status"
    Check "cmd.exe: python runs $older" ($cmdMatrix.Out -match "Python $([regex]::Escape($older))") (Show $cmdMatrix)
    Check "cmd.exe: python$Other runs $otherVersion" ($cmdMatrix.Out -match "Python $([regex]::Escape($otherVersion))") (Show $cmdMatrix)
    Check "cmd.exe: manage-python --status" ($cmdMatrix.Out -match "manage-python $([regex]::Escape($Version))") (Show $cmdMatrix)
    foreach ($shell in $Shells) {
        $matrix = Invoke-PsDefault $shell.Exe "python --version; python$Other --version; manage-python --status; exit `$LASTEXITCODE"
        Capture "every alias from $($shell.Name)" (Show $matrix)
        Check "$($shell.Name): python runs $older" ($matrix.Out -match "Python $([regex]::Escape($older))") (Show $matrix)
        Check "$($shell.Name): python$Other runs $otherVersion" ($matrix.Out -match "Python $([regex]::Escape($otherVersion))") (Show $matrix)
        Check "$($shell.Name): manage-python --status exits 0" ($matrix.Code -eq 0 -and $matrix.Out -match "manage-python $([regex]::Escape($Version))") (Show $matrix)
    }

    # -- [13] Aliases written as .ps1 by 1.0.2 and earlier are removed ---------
    Section "13 Files written by 1.0.2 for PowerShell are retired"
    $legacy = "#`n# source`n#   project: osat-manager-python`n#   path: scripts/windows/alias.ps1.template`n# generated`n#   path: %LOCALAPPDATA%\Programs\python.ps1`n#   by: manage-python.py`n#`n"
    Write-Text (Join-Path $Programs "python.ps1") $legacy -Crlf
    # After section 9's rename the switched line's alias is py312.
    Write-Text (Join-Path $Programs "py312.ps1") "& py.exe @args`n" -Crlf
    $r = Manage "--switch $newest"
    Capture "--switch $newest with old .ps1 aliases present" (Show $r)
    Check "--switch removes a .ps1 alias the manager wrote" ($r.Code -eq 0 -and -not (Test-Path (Join-Path $Programs "python.ps1"))) (Show $r)
    Check "--switch leaves a .ps1 it did not write, with a warning" ((Test-Path (Join-Path $Programs "py312.ps1")) -and $r.Err.Contains("PowerShell runs it instead")) (Show $r)
    Remove-Item (Join-Path $Programs "py312.ps1")

    # 1.0.2 also wrote the pointer as python-manager.env.ps1, and its .ps1
    # aliases read an operator env.ps1. The pointer copy is deleted; the
    # operator's env.ps1 is left, with a warning shown once.
    $oldPointer = Join-Path $Share "python-manager.env.ps1"
    $operatorPs1 = Join-Path $OperatorDir "env.ps1"
    Write-Text $oldPointer "# %LOCALAPPDATA%\python-manager\python-manager.env.ps1`n# Generated by manage-python.py. Read by the aliases at runtime.`n" -Crlf
    New-Item -ItemType Directory -Path $OperatorDir -Force | Out-Null
    Write-Text $operatorPs1 "`$env:OSAT_EXAMPLE = 'set by the operator'`n" -Crlf
    $r = Manage "--switch $older"
    Capture "--switch $older with the 1.0.2 pointer and an operator env.ps1 present" (Show $r)
    Check "--switch deletes the pointer's .ps1 copy" ($r.Code -eq 0 -and -not (Test-Path $oldPointer)) (Show $r)
    Check "the operator's env.ps1 is left in place" (Test-Path $operatorPs1)
    Check "a warning says env.ps1 is no longer read" ($r.Err.Contains("is no longer read")) (Show $r)
    $again = Manage "--switch $newest"
    Check "the warning is shown once" ($again.Code -eq 0 -and -not $again.Err.Contains("is no longer read")) (Show $again)
    Remove-Item $operatorPs1
}
catch {
    Check "the validation script ran to the end" $false ($_ | Out-String)
}
finally {
    $manual = @"

[Manual steps: record each result here]
  M1  New terminal from the Start menu: where.exe python; Get-Command python -All; python --version
      result:
  M2  cmd.exe, python REPL, Ctrl+C at the prompt, then Ctrl+C during: python -c "import time; time.sleep(30)"
      Is "Terminate batch job (Y/N)?" shown? What happens after answering?
      result:
  M3  Windows PowerShell 5.1, then PowerShell 7: the same two Ctrl+C tests, calling python by name (the .cmd alias).
      Is "Terminate batch job (Y/N)?" shown? Does the PowerShell prompt come back normally afterwards?
      result:
  M4  rundll32 sysdm.cpl,EditEnvironmentVariables  opens, and user Path shows %LOCALAPPDATA%\Programs first
      result:
  M5  Sign out and in: a new terminal still runs python and manage-python
      result:
  M6  Only if section 11 was skipped: install PowerShell 7, open it, run cmd, then from the release folder:
      powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 --install <a version from --status>
      Did it finish without "is not recognized"? What did  powershell -NoProfile -Command "`$env:PSModulePath"  print?
      result:
"@
    $elapsed = [int]([DateTime]::UtcNow - $Started).TotalSeconds
    Say ""
    if ($Failures.Count -eq 0) { Say "RESULT: all automated checks passed in $elapsed s. Complete the manual steps below." }
    else { Say "RESULT: $($Failures.Count) check(s) failed in $elapsed s: $($Failures -join '; ')" }
    $all = New-Object System.Collections.Generic.List[string]
    $all.AddRange($Report)
    $all.Add($manual)
    $all.Add("")
    $all.Add("[Captured output]")
    $all.AddRange($Captured)
    Write-Text $ReportPath (($all -join "`n") + "`n") -Crlf
    Write-Host ""
    Write-Host "Report: $ReportPath"
}
if ($Failures.Count -gt 0) { exit 1 }
exit 0
