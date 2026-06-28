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
- Source distributions do not ship a wirelog binary; source installs use
  the same loader check against the libwirelog found at runtime.
- Wheels bundle a `libwirelog` built from the validated ref via
  `auditwheel` / `delocate` / `delvewheel`.

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
| `1.0.0`         | `0.44.0`        | `272edf3a24b25676f12c4b843d55510f5048dd2f` | Validated against wirelog `v0.50.0` (peeled tag SHA); runtime minimum remains `0.44.0`. |
| `1.0.1`         | `0.44.0`        | `0c6e0cdaee7db069be5d8d896bb59bdcb15673e9` | Validated against wirelog `v0.51.0` (peeled tag SHA); runtime minimum remains `0.44.0`. Bundled engine bumped to pick up the wirelog#914 single-body-rule derivation fix (#165). |
| `1.0.2`         | `0.44.0`        | `0c6e0cdaee7db069be5d8d896bb59bdcb15673e9` | Validated against wirelog `v0.51.0` (peeled tag SHA); runtime minimum remains `0.44.0`. PyreWire-only maintenance release (CI action bumps, SPDX headers, docs); no engine change. |
| `1.0.3`         | `0.52.0`        | `da82a14a7e1472e33aa6ed753b3bc3dfe28a68ba` | Validated against wirelog `v0.52.0` (peeled tag SHA); runtime minimum raised to `0.52.0`. Bundled engine bumped to v0.52.0 and the loader floor moved up to match. |

The table grows with every release; the source of truth is the
[CHANGELOG](https://github.com/semantic-reasoning/PyreWire/blob/main/CHANGELOG.md).
