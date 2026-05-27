# Changelog

All notable changes to PyreWire are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). PyreWire and
wirelog version independently; each PyreWire release declares a single
supported wirelog `MAJOR.MINOR` series (see
[versioning rule](docs/versioning.md)).

## [Unreleased]

## [1.0.0] - 2026-05-27

### Added
- PyreWire 1.0.0 is the first stable release of the Python wrapper for
  wirelog. It establishes the supported public API boundary for the
  `pyrewire` package and marks v1.0.x as the security-supported release
  line.
- Stable top-level exports now include:
  - incremental session classes: `EasySession` and `Session`;
  - batch execution classes: `BatchProgram` and `Result`;
  - program and introspection wrappers: `Program`, `Schema`, `Column`,
    `Stratum`, and `IRNode`;
  - async wrappers: `AsyncEasySession`, `AsyncSession`, and
    `AsyncBatchProgram`;
  - IO adapter exports: `IOContext`, `register_adapter`,
    `unregister_adapter`, and `registered_schemes`;
  - compound wrappers: `Compound` and `CompoundArg`;
  - exported enums, errors, and helpers, including `ErrorCode`,
    `ColumnType`, `CompoundKind`, `IRNodeType`, `WirelogError`
    subclasses, `wirelog_version`, `build_config`, `Delta`, and
    `make_safe_print_delta`.
- Incremental session capabilities are validated against wirelog
  v0.44.0. `EasySession` and `Session` support step/snapshot workflows,
  and `AsyncSession` provides the async incremental session surface.

### Changed
- Package metadata is now versioned as `1.0.0` with the
  `Development Status :: 5 - Production/Stable` classifier.
- PyreWire follows semantic-versioning expectations for the stable
  public API. Backward-incompatible changes require a new major version;
  deprecated public APIs will remain available for at least one minor
  release before removal unless a security or correctness issue makes
  that impossible.
- The README quickstart and `docs/` now describe the v1 public API:
  `BatchProgram` for one-shot closure and `EasySession` / `Session` for
  incremental step/snapshot work. The old `Program`-builder examples
  were replaced with the supported APIs, and the README badges now
  match the `ci` and `docs` workflows (#122).
- GitHub release automation extracts this exact tagged changelog section
  for release notes instead of publishing the full changelog body.

### Support
- Supported Python versions are CPython 3.11, 3.12, 3.13, and 3.14.
  Python 3.10 is not supported by the v1.0 release line.
- Published wheels are built for Linux `manylinux_2_28` `x86_64`,
  macOS `arm64` only, and Windows `AMD64`.
- Wheels bundle `libwirelog`, so wheel installs do not require a
  separate wirelog installation.
- Source distributions do not bundle `libwirelog`. Source installs need
  a compatible system `libwirelog` discoverable by the loader, or an
  explicit `WIRELOG_LIB` path.
- PyreWire 1.0.0 is validated against wirelog v0.44.0 at peeled SHA
  `5bebc8d40bbb850179fbb091807964762df5a814`; the minimum compatible
  runtime wirelog version is 0.44.0. This wirelog release includes the
  recursive aggregation residue fix needed for the stable
  step/snapshot API.
- Release, test, and wheel automation runs on `ubuntu-24.04`,
  `macos-15`, and `windows-2025-vs2026` with Python 3.11-3.14.

## [0.41.0] - 2026-05-21

### Added
- FFI bootstrap (#2): libwirelog discovery and runtime version
  verification with `WirelogVersionUnavailableWarning` fallback for
  pre-#841 builds.
- Typed exception hierarchy (#4): `WirelogError` and subclasses,
  `check(rc)` helper, `error_string(rc)` with local fallback table.
- ctypes types / enums / callbacks (#3) and the shared libc
  allocator helper (#41).
- `EasySession` (#9): lifecycle, intern table, `insert` / `remove`,
  and the variadic `insert_sym` / `remove_sym` wrappers (#44).
  `set_delta_callback` / `step` / `snapshot` were not part of 0.41.0;
  they required wirelog#852 and became available once wirelog `0.44.0`
  was pinned (see [1.0.0]).
- `Session` (advanced, #21): backend selection, worker count,
  batched `insert` / `remove`, `step`, `snapshot`, `set_delta_callback`,
  one-way mode machine, NumPy zero-copy `insert_batch` / `remove_batch`
  (#22), `make_compound` (#23), `seed_intern`.
- `BatchProgram` + `Result` (#17 / #18): parse → optimize → evaluate,
  per-relation CSV write, schema-driven row decoding.
  `BatchProgram.load_all_facts` / `load_input_files` /
  `optimizer_debug` via the C-level stdout capture (#19).
- `Program` / `Schema` / `Stratum` (#14) with inline-fact extraction
  (#15) and `preview_inline_facts` + `insert_with_dedupe` (#47).
- `IRNode` lazy tree wrapper (#25) layered on the IR FFI bindings (#24).
- `@register_adapter` decorator for Python-defined IO adapters
  bridged to wirelog's ABI v2 (#26 + #27).
- `Compound` wrapper with weakref-based session-scope invalidation
  (#23); `CompoundBusyError` / `CompoundSaturatedError` surface
  through `check(rc)`.
- `AsyncEasySession`, `AsyncSession`, `AsyncBatchProgram` (#29) —
  asyncio proxies that run every wirelog call on a per-instance
  single-worker thread.
- mkdocs-material documentation site with mkdocstrings auto-rendered
  reference (#34) and a four-page semantics guide (#36).
- CI: lint gate (black / isort / flake8 / ruff / mypy) → test matrix
  (Ubuntu 24.04 / macOS-15 / Windows 2025 VS 2026 × py3.11-3.14) → 90 % coverage floor (#38 / #39 / #40).
- Distribution: MANIFEST.in excludes wirelog binaries from sdists
  (#51); wheel-bundling matrix and cibuildwheel config tracked in
  #30 / #31 / #32 / #33.

### Notes
- This release matches wirelog `v0.41.0`. The wheel bundles
  `libwirelog.so.1` (or the platform equivalent); no system install
  is required.
- Arrow zero-copy interop is **deferred** to a follow-up release.
  Tracked in #50.
- `EasySession.step` / `snapshot` and the `step` / `snapshot`
  mirrors on `AsyncEasySession` are not in 0.41.0 — they require
  wirelog#852. They became available after the `v0.44.0` wirelog pin
  (see [1.0.0]). Tracked in wirelog#859.

[Unreleased]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/semantic-reasoning/PyreWire/compare/v0.41.0...v1.0.0
[0.41.0]: https://github.com/semantic-reasoning/PyreWire/releases/tag/v0.41.0
