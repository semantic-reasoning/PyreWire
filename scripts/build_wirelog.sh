#!/usr/bin/env bash
# Build wirelog from source at the matching tag.
#
# Inputs (env):
#   WIRELOG_VERSION  - tag / branch name to check out (default: 0.40.99)
#   WIRELOG_PREFIX   - install prefix (default: /wirelog-install)
#   WIRELOG_REPO     - git URL (default: https://github.com/semantic-reasoning/wirelog)
#   WIRELOG_SRC      - working source dir (default: $TMPDIR/wirelog-src or /tmp/wirelog-src)
#
# Output:
#   libwirelog installed into $WIRELOG_PREFIX/lib (and headers under .../include).
#
# This script is consumed by .github/workflows/ci.yml (#38) and refined
# further by the wheel-build pipeline (#30).
set -euo pipefail

WIRELOG_VERSION="${WIRELOG_VERSION:-0.40.99}"
WIRELOG_PREFIX="${WIRELOG_PREFIX:-/wirelog-install}"
WIRELOG_REPO="${WIRELOG_REPO:-https://github.com/semantic-reasoning/wirelog}"
WIRELOG_SRC="${WIRELOG_SRC:-${TMPDIR:-/tmp}/wirelog-src}"

echo "wirelog: version=$WIRELOG_VERSION prefix=$WIRELOG_PREFIX"

rm -rf "$WIRELOG_SRC"
git clone --depth 1 --branch "$WIRELOG_VERSION" "$WIRELOG_REPO" "$WIRELOG_SRC"

meson setup "$WIRELOG_SRC/builddir" "$WIRELOG_SRC" \
    --prefix="$WIRELOG_PREFIX" \
    --buildtype=release \
    --libdir=lib \
    -Dtests=false

# PyreWire's CI only needs `libwirelog` itself. Skip the example binaries
# (each example/<NN>/ subdir builds an executable). wirelog 0.40.99 has
# no `examples` meson option yet, so we filter by ninja target instead of
# rebuilding the whole tree. Tracked: an upstream `examples` option would
# let us drop the grep step.
mapfile -t targets < <(
    meson introspect --targets "$WIRELOG_SRC/builddir" \
        | jq -r '.[] | select(.type=="shared library" or .type=="static library") | .name'
)
if [ ${#targets[@]} -gt 0 ]; then
    meson compile -C "$WIRELOG_SRC/builddir" "${targets[@]}"
else
    meson compile -C "$WIRELOG_SRC/builddir"
fi
meson install -C "$WIRELOG_SRC/builddir"

echo "Installed:"
find "$WIRELOG_PREFIX/lib" -maxdepth 2 -name 'libwirelog*' | head
