# Versioning

PyreWire and wirelog version **independently**. PyreWire's version
number tracks PyreWire's own release cadence; the wirelog releases
it can run against are declared separately.

## How compatibility is declared

Each PyreWire build supports exactly one wirelog `MAJOR.MINOR` series.
The series is encoded in `COMPATIBLE_WIRELOG_SERIES` inside
`src/pyrewire/_ffi/_loader.py`. The loader rejects any libwirelog
whose reported version falls outside that series with
`WirelogVersionError`.

- Patch releases inside the series (e.g. `0.43.0`, `0.43.1`, `0.43.99`)
  are accepted interchangeably.
- A different minor (e.g. `0.42.x`, `0.44.x`) or major is rejected,
  even if the ABI happens to match.

## Why

wirelog's ABI is not yet stable. PyreWire validates against a single
minor series at a time; mixing in releases from a different series
is undefined behaviour. The loader check enforces this end-to-end:

- `WIRELOG_VERSION` in CI pins the exact tag CI builds and tests
  against.
- `COMPATIBLE_WIRELOG_SERIES` in the loader rejects out-of-series
  builds at import time.
- Wheels bundle a matching `libwirelog.so.X` via `auditwheel` /
  `delocate` / `delvewheel`.

## PyreWire-only changes

A PyreWire-only fix (Python-side bug that does not need a new
wirelog) is a plain PyreWire patch bump; the supported wirelog
series is unaffected.

## Moving to a new wirelog series

When PyreWire is rebuilt and re-validated against a new wirelog
minor series:

1. Update `WIRELOG_VERSION` in CI / `pyproject.toml` cibuildwheel
   sections to the new tag.
2. Update `COMPATIBLE_WIRELOG_SERIES` in `_loader.py` to the new
   `(major, minor)`.
3. Record the change in the CHANGELOG.

PyreWire's own `__version__` is bumped only when there is a PyreWire
release to publish; it is **not** tied to the wirelog change.

## Compatibility table

| PyreWire        | Supported wirelog series | Notes                       |
| --------------- | ------------------------ | --------------------------- |
| `0.41.99`       | `0.41.x`                 | Independent versioning.     |

The table grows with every release; the source of truth is the
[CHANGELOG](https://github.com/semantic-reasoning/PyreWire/blob/main/CHANGELOG.md).
