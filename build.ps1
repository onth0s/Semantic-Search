# build.ps1 - build + link sempath so `sempath` runs this working tree.
# No parameters, no flags. Safe to re-run: if the link is already healthy it
# is a no-op.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

# --- preconditions ------------------------------------------------------
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "py launcher not found on PATH."
}
if (-not (Test-Path "$root\pyproject.toml")) { throw "pyproject.toml missing - wrong directory." }
if (-not (Test-Path "$root\sempath\__main__.py")) { throw "sempath package missing - wrong directory." }

# --- is it already linked to THIS repo? ---------------------------------
$show = & py -3.13 -m pip show sempath 2>$null
$line = $show | Where-Object { $_ -like 'Editable project location:*' }
$editable = if ($line) { ($line -split ':', 2)[1].Trim() } else { $null }

$cmd = Get-Command sempath -ErrorAction SilentlyContinue
$shadows = $cmd -and $cmd.Source -like "$root\dist\*" # stale PyInstaller build winning on PATH
$linked =
    $editable -and
    (Test-Path $editable) -and
    ((Resolve-Path $editable).Path -eq $root) -and
    $cmd -and
    -not $shadows

if ($shadows) {
    Write-Warning "PATH is resolving sempath to $cmd.Source (stale PyInstaller build)."
}

# --- build + link, only if not already linked --------------------------
if ($linked) {
    Write-Host "Already linked: sempath -> $editable" -ForegroundColor Green
} else {
    Write-Host "Building + linking sempath into py -3.13 ..." -ForegroundColor Cyan
    & py -3.13 -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed (exit $LASTEXITCODE)." }
}

# --- verify the link ---------------------------------------------------
$cmd = Get-Command sempath -ErrorAction SilentlyContinue
if (-not $cmd) { throw "sempath is not on PATH after install." }
Write-Host "Linked shim: $($cmd.Source)" -ForegroundColor Green
& sempath --version
if ($LASTEXITCODE -ne 0) { throw "sempath --version failed (exit $LASTEXITCODE)." }
