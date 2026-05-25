# PowerShell port of `scripts/build_wirelog.sh` (#30).
# Builds wirelog from source at the matching tag and installs it into
# the prefix used by the wheel-bundling step.
#
# Inputs (env):
#   WIRELOG_VERSION  - tag / branch name / commit SHA to check out (default: main)
#   WIRELOG_PREFIX   - install prefix (default: C:\wirelog-install)
#   WIRELOG_REPO     - git URL (default: https://github.com/semantic-reasoning/wirelog)

$ErrorActionPreference = "Stop"

$WirelogVersion = if ($env:WIRELOG_VERSION) { $env:WIRELOG_VERSION } else { "main" }
$Prefix = if ($env:WIRELOG_PREFIX) { $env:WIRELOG_PREFIX } else { "C:\wirelog-install" }
$Repo   = if ($env:WIRELOG_REPO)   { $env:WIRELOG_REPO }   else { "https://github.com/semantic-reasoning/wirelog" }
$Src    = "$env:TEMP\wirelog-src"

Write-Host "==> wirelog version: $WirelogVersion"
Write-Host "==> install prefix: $Prefix"
Write-Host "==> source dir:     $Src"

if (Test-Path $Src) {
    Remove-Item -Recurse -Force $Src
}

# `--branch` accepts tags and branch names. For exact commit pins, fetch
# just that object and detach HEAD there.
git ls-remote --exit-code --heads --tags $Repo $WirelogVersion *> $null
if ($LASTEXITCODE -eq 0) {
    git clone --depth 1 --branch $WirelogVersion $Repo $Src
} else {
    git clone --filter=blob:none --no-checkout $Repo $Src
    git -C $Src fetch --depth 1 origin $WirelogVersion
    git -C $Src checkout --detach FETCH_HEAD
}

# Build with tests disabled — PyreWire's CI only needs the library
# and the public headers. wirelog v0.41.0 has no `examples` meson
# option (it was added on a later branch), so we limit compilation
# to the `wirelog` target instead; that pulls in its subproject
# deps (nanoarrow, libxxhash) but skips the example binaries.
pip install --upgrade meson ninja

meson setup "$Src\builddir" $Src `
    --prefix=$Prefix `
    --buildtype=release `
    -Dtests=false
meson compile -C "$Src\builddir" wirelog
# Run `meson install` without `--skip-subprojects` so the wirelog DLL's
# co-located runtime deps (nanoarrow.dll, libxxhash.dll) end up in
# `$Prefix\bin\` next to it. ctypes loads wirelog-1.dll by absolute
# path, which uses LOAD_WITH_ALTERED_SEARCH_PATH on Windows and so
# finds dependent DLLs in the same directory.
meson install -C "$Src\builddir"

Write-Host "wirelog installed to $Prefix"
