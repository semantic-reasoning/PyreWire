# PowerShell port of `scripts/build_wirelog.sh` (#30).
# Builds wirelog from source at the matching tag and installs it into
# the prefix used by the wheel-bundling step.
#
# Inputs (env):
#   WIRELOG_VERSION  - tag / branch name to check out (default: v0.41.0)
#   WIRELOG_PREFIX   - install prefix (default: C:\wirelog-install)
#   WIRELOG_REPO     - git URL (default: https://github.com/semantic-reasoning/wirelog)

$ErrorActionPreference = "Stop"

$WirelogVersion = if ($env:WIRELOG_VERSION) { $env:WIRELOG_VERSION } else { "v0.41.0" }
$Prefix = if ($env:WIRELOG_PREFIX) { $env:WIRELOG_PREFIX } else { "C:\wirelog-install" }
$Repo   = if ($env:WIRELOG_REPO)   { $env:WIRELOG_REPO }   else { "https://github.com/semantic-reasoning/wirelog" }
$Src    = "$env:TEMP\wirelog-src"

Write-Host "==> wirelog version: $WirelogVersion"
Write-Host "==> install prefix: $Prefix"
Write-Host "==> source dir:     $Src"

if (Test-Path $Src) {
    Remove-Item -Recurse -Force $Src
}

# `--branch` accepts both tags and branch names, so the same script
# serves CI's pinned tag (`v0.41.0`) and the nightly's `main`.
git clone --depth 1 --branch $WirelogVersion $Repo $Src

# Build with tests + examples disabled — PyreWire's CI only needs the
# library and the public headers.
pip install --upgrade meson ninja

meson setup "$Src\builddir" $Src `
    --prefix=$Prefix `
    --buildtype=release `
    -Dtests=false `
    -Dexamples=false
meson compile -C "$Src\builddir"
meson install -C "$Src\builddir"

Write-Host "wirelog installed to $Prefix"
