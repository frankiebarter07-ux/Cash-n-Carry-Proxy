<#
    Set this Windows PC up as the collector for Booker prices.

    WHY THIS EXISTS
    Booker returns "403 Access Denied" to GitHub's cloud runners because they use
    datacenter IP addresses, which bot filters distrust by default. The prices are
    public; the problem is only *where the request comes from*. This registers this
    machine as a GitHub Actions runner, so the daily job's Booker step runs from the
    office's ordinary internet connection and Booker serves the real page.

    Everything else is unchanged: same repository, same workflows, same logs in the
    Actions tab. Only the Booker step moves here.

    WHAT YOU NEED FIRST
      1. This PC left switched on (it only wakes for a minute or two each morning).
      2. A registration token from the repository:
           Settings -> Actions -> Runners -> New self-hosted runner -> Windows
         Copy the long token shown under "Configure". It expires after one hour,
         so fetch it just before running this.
      3. This window opened as Administrator:
           Start -> type "PowerShell" -> right-click -> Run as administrator

    HOW TO RUN
      cd path\to\Cash-n-Carry-Proxy
      .\tools\setup-windows-runner.ps1 -Token AXXXXXXXXXXXXXXXXXXXXXXXXXXXX

    SECURITY -- PLEASE READ
    A self-hosted runner executes whatever code the repository's workflows contain.
    That is safe for a private repository that only your team can change, which is
    what this is. Do NOT make the repository public while this runner is attached,
    and do not attach this runner to a repository that accepts outside pull
    requests -- a stranger's pull request could then run code on this machine.

    TO REMOVE IT LATER
      cd C:\actions-runner
      .\config.cmd remove --token <a fresh token from the same settings page>
#>

[CmdletBinding()]
param(
    # The registration token from Settings -> Actions -> Runners -> New self-hosted runner.
    [Parameter(Mandatory = $true)]
    [string] $Token,

    # The repository this runner serves.
    [string] $Repo = "frankiebarter07-ux/Cash-n-Carry-Proxy",

    # Where to install. Keep it short and outside any synced folder (OneDrive etc).
    [string] $Dir = "C:\actions-runner"
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok  ($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# --- 0. checks that save a confusing failure later ---------------------------
Step "Checking prerequisites"

$admin = ([Security.Principal.WindowsPrincipal] `
          [Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    throw "Not running as Administrator. Close this window, then: Start -> PowerShell -> right-click -> Run as administrator."
}
Ok "Administrator: yes"

if ([Environment]::Is64BitOperatingSystem -ne $true) {
    throw "This script installs the 64-bit runner and this PC reports 32-bit Windows."
}
Ok "64-bit Windows: yes"

# Git and Python are needed by the workflow itself, not by the runner install.
# Install them now so the first collection at 06:00 doesn't fail unattended.
foreach ($tool in @(
        @{ Name = "git";    Cmd = "git";    Winget = "Git.Git" },
        @{ Name = "Python"; Cmd = "python"; Winget = "Python.Python.3.12" })) {

    if (Get-Command $tool.Cmd -ErrorAction SilentlyContinue) {
        Ok "$($tool.Name): already installed"
        continue
    }
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Warn "$($tool.Name) not found -- installing via winget"
        winget install --id $($tool.Winget) --silent --accept-package-agreements --accept-source-agreements
        Ok "$($tool.Name): installed (a reboot may be needed for PATH to update)"
    } else {
        Warn "$($tool.Name) is missing and winget is unavailable on this PC."
        Warn "Install it by hand, then re-run this script:"
        if ($tool.Name -eq "git") { Warn "  https://git-scm.com/download/win" }
        else                      { Warn "  https://www.python.org/downloads/windows/  (tick 'Add python.exe to PATH')" }
        throw "Missing prerequisite: $($tool.Name)"
    }
}

# --- 1. fetch the current runner release -------------------------------------
Step "Finding the latest GitHub Actions runner"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/actions/runner/releases/latest" `
                             -Headers @{ "User-Agent" = "oil-index-setup" }
$version = $release.tag_name.TrimStart("v")
$zipName = "actions-runner-win-x64-$version.zip"
$zipUrl  = "https://github.com/actions/runner/releases/download/v$version/$zipName"
Ok "Version $version"

# --- 2. download and unpack ---------------------------------------------------
Step "Installing to $Dir"

if (Test-Path (Join-Path $Dir "config.cmd")) {
    throw "A runner is already installed at $Dir. Remove it first (see the header of this script), or pass a different -Dir."
}
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$zipPath = Join-Path $Dir $zipName

Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
Ok "Downloaded $([math]::Round((Get-Item $zipPath).Length / 1MB)) MB"

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $Dir)
Remove-Item $zipPath
Ok "Unpacked"

# Keep Playwright's browsers inside the runner folder rather than in the service
# account's user profile, which a Windows service may not have. The runner reads
# this .env on every job.
$browsers = Join-Path $Dir "pw-browsers"
New-Item -ItemType Directory -Force -Path $browsers | Out-Null
Set-Content -Path (Join-Path $Dir ".env") -Encoding ASCII `
            -Value "PLAYWRIGHT_BROWSERS_PATH=$browsers"
Ok "Chromium will be stored in $browsers"

# --- 3. register with the repository and install the service ------------------
Step "Registering with $Repo"

Push-Location $Dir
try {
    $name = "$env:COMPUTERNAME-oil-collector"
    & .\config.cmd --unattended `
                   --url    "https://github.com/$Repo" `
                   --token  $Token `
                   --name   $name `
                   --labels "self-hosted,windows,oil-collector" `
                   --work   "_work" `
                   --runasservice
    if ($LASTEXITCODE -ne 0) {
        throw "Registration failed (exit $LASTEXITCODE). The usual cause is an expired token -- they last one hour. Fetch a fresh one and re-run."
    }
    Ok "Registered as '$name'"

    # config.cmd installs the service; make sure it is actually running and set to
    # start automatically after a power cut or a Windows update reboot.
    $svc = Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue |
           Select-Object -First 1
    if ($svc) {
        Set-Service -Name $svc.Name -StartupType Automatic
        if ($svc.Status -ne "Running") { Start-Service -Name $svc.Name }
        Ok "Service '$($svc.Name)' running, set to start automatically on boot"
    } else {
        Warn "Could not find the runner service. Check Services (services.msc) for a name starting 'actions.runner'."
    }
} finally {
    Pop-Location
}

# --- 4. what to do next -------------------------------------------------------
Step "Done"
Write-Host @"

    ONE MORE STEP -- the Booker job stays switched off until you do this:

      On GitHub: Settings -> Secrets and variables -> Actions -> Variables
      -> New repository variable
         Name:  BOOKER_RUNNER
         Value: true

    Until that variable exists the daily job skips Booker on purpose, and the index
    publishes the other four sellers. (A job pointed at a runner that isn't there
    does not fail -- it queues for 24 hours and stalls the whole pipeline.)

    Confirm it works, without waiting for tomorrow morning:

      1. Open the repository on github.com -> Actions tab
      2. Choose "Test adapters" -> Run workflow
      3. Set 'runner' to: self-hosted
      4. Run it, then open the log

    Success looks like four Booker lines, each with a tick, a price, and the
    method "embedded-json:collectOE" -- for example:

        rapeseed/bib: 33.99  via embedded-json:collectOE

    Today those same four lines read "no labelled price ... Access Denied".

    If Booker still shows 403 / Access Denied, this PC's internet connection is
    also being filtered -- try a different network (for example a phone hotspot)
    to confirm, and see HANDOVER.md section 3.

    From then on it is automatic: the daily job at 06:00 UTC collects the four
    cloud sellers on GitHub's runners and Booker on this machine, then merges
    them. This PC only needs to be switched on.

"@ -ForegroundColor Gray
