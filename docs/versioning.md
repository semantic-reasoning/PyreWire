# Versioning

PyreWire's version number is **pinned to the wirelog version it
wraps**. A PyreWire release labelled `0.41.0` always wraps the
matching wirelog `v0.41.0` tag — never a `main` snapshot, never a
different upstream release.

## Why

wirelog's ABI is not yet stable. Mixing PyreWire built against one
wirelog version with a different `libwirelog.so.X` is undefined
behaviour at best and a segfault at worst. Strict version lockstep
keeps that surface enforceable end-to-end:

- The CI pipeline pins `WIRELOG_VERSION` to the same tag as the
  PyreWire release.
- The loader (`pyrewire._ffi._loader`) verifies the runtime
  `libwirelog` matches the version PyreWire was built against, and
  raises `WirelogVersionError` otherwise.
- Wheels bundle the matching `libwirelog.so.X` (`auditwheel` /
  `delocate` / `delvewheel`), so a `pip install pyrewire==0.41.0`
  pulls in exactly one ABI-compatible pair.

## PyreWire-only hotfixes

PyreWire-only fixes (e.g. a Python-side bug that does not need a new
wirelog release) use **PEP 440 build metadata**:

- `0.41.0` — initial release wrapping wirelog `v0.41.0`.
- `0.41.0.post1` — PyreWire-only patch, still wraps wirelog `v0.41.0`.
- `0.41.1` — released only when wirelog `v0.41.1` exists; PyreWire
  rebuilds against it.

## Compatibility table

| PyreWire        | wirelog          | Notes                        |
| --------------- | ---------------- | ---------------------------- |
| `0.41.0`        | `v0.41.0`        | Initial public release.      |

The table grows with every release; the source of truth is the
[CHANGELOG](https://github.com/semantic-reasoning/PyreWire/blob/main/CHANGELOG.md).
