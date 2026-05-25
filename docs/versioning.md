# Versioning

PyreWire and wirelog version **independently**. PyreWire's version
number tracks PyreWire's own release cadence; the wirelog releases
it can run against are declared separately.

## How compatibility is declared

Each PyreWire build declares the oldest wirelog version it supports in
`MINIMUM_WIRELOG_VERSION` inside `src/pyrewire/_ffi/_loader.py`. The
loader rejects any libwirelog whose reported version is older than that
floor with `WirelogVersionError`.

- The minimum and newer releases are accepted, including main-branch
  snapshots such as `0.44.99`.
- Older releases are rejected because they may lack parser behavior or
  public symbols PyreWire now relies on.

## Why

wirelog's ABI is not yet stable. PyreWire validates CI and wheels
against an exact wirelog source ref, while the loader keeps the lower
bound explicit so developers can run newer main builds locally:

- `WIRELOG_VERSION` in CI pins the exact wirelog ref CI builds and tests
  against.
- `MINIMUM_WIRELOG_VERSION` in the loader rejects too-old builds at
  import time.
- Wheels bundle a matching `libwirelog.so.X` via `auditwheel` /
  `delocate` / `delvewheel`.

## PyreWire-only changes

A PyreWire-only fix (Python-side bug that does not need a new
wirelog) is a plain PyreWire patch bump; the supported wirelog floor is
unaffected.

## Moving to a new wirelog series

When PyreWire is rebuilt and re-validated against a new wirelog ref:

1. Update `WIRELOG_VERSION` in CI / `pyproject.toml` cibuildwheel
   sections to the new tag, branch, or commit SHA.
2. Update `MINIMUM_WIRELOG_VERSION` in `_loader.py` only if the new
   PyreWire code stops supporting older wirelog builds.
3. Record the change in the CHANGELOG.

PyreWire's own `__version__` is bumped only when there is a PyreWire
release to publish; it is **not** tied to the wirelog change.

## Compatibility table

| PyreWire        | Minimum wirelog | Validated wirelog ref                      | Notes                   |
| --------------- | --------------- | ------------------------------------------ | ----------------------- |
| `0.41.99`       | `0.44.0`        | `5bebc8d40bbb850179fbb091807964762df5a814` | Pins wirelog `v0.44.0`. |

The table grows with every release; the source of truth is the
[CHANGELOG](https://github.com/semantic-reasoning/PyreWire/blob/main/CHANGELOG.md).
