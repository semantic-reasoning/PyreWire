# Support Matrix

This page documents the supported PyreWire v1.0 installation targets.
It is a release contract, not a list of every platform that might work
from source.

## Python

PyreWire v1.0 supports CPython 3.11, 3.12, 3.13, and 3.14.

## Wheels

Published wheels bundle `libwirelog`; users installing those wheels do
not need to install wirelog separately.

| Platform | Wheel target | Build and test runner | Notes |
| -------- | ------------ | --------------------- | ----- |
| Linux | `manylinux_2_28` `x86_64` | `ubuntu-24.04` | Built with cibuildwheel's manylinux container and repaired with auditwheel. |
| macOS | `arm64` | `macos-15` | Apple Silicon only for v1.0; no macOS Intel or universal2 wheel is produced. |
| Windows | `win_amd64` / `AMD64` | `windows-2025-vs2026` | Built with MSVC and repaired with delvewheel. |

The bundled library is built from wirelog v0.44.0, using peeled SHA
`5bebc8d40bbb850179fbb091807964762df5a814`.

## Source Distributions

Source distributions do not bundle `libwirelog`. A source install needs
a compatible system `libwirelog` that PyreWire can discover at runtime.
The minimum compatible wirelog version is >= 0.44.0.

PyreWire searches for `libwirelog` through its normal loader order,
including the system dynamic linker and `pkg-config`. Set `WIRELOG_LIB`
to the explicit path of a compatible library when automatic discovery is
not enough.
