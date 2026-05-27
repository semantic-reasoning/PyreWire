# Changelog

All notable changes to PyreWire are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). PyreWire and
wirelog version independently; each PyreWire release declares a single
supported wirelog `MAJOR.MINOR` series (see
[versioning rule](docs/versioning.md)).

## [Unreleased]

### Notes
- Drops Python 3.10 support; PyreWire now supports Python 3.11+.
- Adds Python 3.14 to the CI and wheel-install matrices.
- Moves GitHub Actions Ubuntu runners to `ubuntu-24.04`.
- Moves GitHub Actions macOS and Windows matrix runners to `macos-15`
  and `windows-2025-vs2026`.
- Updates GitHub-maintained workflow actions to `actions/checkout@v5`
  `actions/setup-python@v6`, and `actions/cache@v5`; replaces the
  MSVC setup action with an in-step `VsDevCmd.bat` invocation.
- Pins validated wirelog builds to the `v0.44.0` release commit
  (`5bebc8d40bbb850179fbb091807964762df5a814`), which includes
  wirelog#852 (recursive aggregation residue fix), and raises the
  runtime minimum to wirelog `0.44.0`. Tracked in wirelog#859.

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
  `set_delta_callback` / `step` / `snapshot` deferred to the next
  release; tracked alongside wirelog#852.
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
  wirelog#852 (merged on wirelog `main`, awaiting a tag release).
  Tracked in wirelog#859.

[Unreleased]: https://github.com/semantic-reasoning/PyreWire/compare/v0.41.0...HEAD
[0.41.0]: https://github.com/semantic-reasoning/PyreWire/releases/tag/v0.41.0
