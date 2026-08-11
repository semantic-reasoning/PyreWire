# Changelog

All notable changes to PyreWire are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). PyreWire and
wirelog version independently; each PyreWire release declares a runtime
wirelog floor and a validated wirelog ref (see
[versioning rule](docs/versioning.md)).

## [Unreleased]

## [1.0.5] - 2026-08-11

### Fixed
- `BatchProgram.optimize()` no longer corrupts head bindings for a rule
  with four or more body atoms (#180). The engine's SIP-inserted semijoin
  widened the reported output layout by the right relation's arity, which
  shifted every column resolved above it; the out-of-range lookup fell
  back to column 0, so the last head variable came back as `0` while the
  row count and arity stayed correct. Fixed upstream in wirelog#955 and
  delivered here by the engine bump below. There was nothing to fix in
  PyreWire — `optimize()` is a faithful passthrough — so a source install
  resolving an older system `libwirelog` is still affected.
- `crc32_ethernet()` now agrees with externally computed CRCs. Through
  wirelog 0.53.0 it returned a checksum that matched no stored value, so
  `examples/05_crc32_checksum` classified every frame as corrupt.

### Changed
- The bundled and validated wirelog ref moves from `v0.53.0` to
  `v0.54.0` at peeled SHA
  `9f80877c82564cb92ea45bd6fffc2d681b0e13de`.
- The minimum compatible runtime wirelog version remains `0.52.0`.
  wirelog 0.54.0's public C header change is additive — one appended
  `wirelog_str_fn_t` member and documentation — and the library SONAME is
  unchanged, so no PyreWire code stops supporting `0.52.0`. The PyreWire
  public API is unchanged. Tests covering behavior that only wirelog
  `0.54.0` provides are skipped on older runtimes.
- `EasySession.insert()` now raises when the row is wider or narrower
  than the relation's `.decl`, on the first insert as well as later ones
  (wirelog#1038). Previously a relation's width was whatever its first
  producer supplied: too narrow fabricated a zero column, too wide
  dropped the surplus, both silently.
- Programs that are heavy on joins may evaluate more slowly. wirelog#955
  removes an under-derivation that the previous speed depended on, so
  correct answers cost more than the wrong ones did — upstream measured
  DOOP W=1 at ~94 s before and ~1,414 s after.
- `wirelog_program_get_facts`, `wirelog_io_ctx_num_cols`, and
  `wirelog_io_ctx_col_type` report the *physical* row stride rather than
  the declared column count. The two differ only for a relation declaring
  an `inline` compound column. PyreWire passes all three through
  unchanged, so its own contract is unaffected; an embedder that
  reconstructed the stride from a schema of its own should read wirelog's
  release notes.

## [1.0.4] - 2026-07-31

### Changed
- The bundled and validated wirelog ref moves from `v0.52.0` to
  `v0.53.0` at peeled SHA
  `668f82ad69c2bbfc8e8111839302adf1360f55da`.
- The minimum compatible runtime wirelog version remains `0.52.0`;
  wirelog 0.53.0 does not change the public C headers or library SONAME.
  The PyreWire public API is unchanged.

## [1.0.3] - 2026-06-28

### Changed
- The bundled and validated wirelog ref moves from `v0.51.0` to
  `v0.52.0` at peeled SHA
  `da82a14a7e1472e33aa6ed753b3bc3dfe28a68ba`.
- The minimum compatible runtime wirelog version is raised from `0.44.0`
  to `0.52.0`. `MINIMUM_WIRELOG_VERSION` in the loader now rejects any
  libwirelog older than `0.52.0`, so source installs must provide a
  system `libwirelog` of `0.52.0` or newer. The PyreWire public API is
  unchanged.

## [1.0.2] - 2026-06-19

### Changed
- Bumped the pinned `actions/checkout` GitHub Action from v6 to v7 and
  `pypa/cibuildwheel` from v4.0.0 to v4.1.0 across the CI, wheels, and
  release workflows (#171, #172).

### Added
- Every Python source file now carries an
  `SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later` header, making
  PyreWire's dual license machine-discoverable for REUSE/SPDX tooling and
  downstream redistribution. A contract test enforces the header on all
  source files (#173).
- Expanded the Errors reference documentation: an overview, an error-code
  mapping table, and a usage example for the exception hierarchy.

This is a PyreWire-only maintenance release. The public API is unchanged,
and the bundled and validated wirelog ref remains `v0.51.0` at peeled SHA
`0c6e0cdaee7db069be5d8d896bb59bdcb15673e9` with the minimum compatible
runtime wirelog version remaining `0.44.0`.

## [1.0.1] - 2026-06-13

### Changed
- The bundled and validated wirelog ref moves from `v0.50.0` to
  `v0.51.0` at peeled SHA
  `0c6e0cdaee7db069be5d8d896bb59bdcb15673e9`. This is a wirelog-only
  rebuild: the PyreWire public API is unchanged and the minimum
  compatible runtime wirelog version remains `0.44.0`.

### Fixed
- A rule with a single `relation(...)` body atom now derives its head
  when the program also contains the recursive `edge`/`path` rules.
  Previously such one-condition rules (for example `requires_review(...)`
  and `warning(...)`) were silently missing from `EasySession.step()`
  results. The root cause was a wirelog evaluation bug — the iteration
  context was not reset for non-recursive strata — fixed upstream in
  wirelog#914 and first shipped in wirelog `v0.51.0`. PyreWire performs
  no rule evaluation of its own, so bumping the bundled engine is the
  fix (#165).

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
  v0.50.0. `EasySession` and `Session` support step/snapshot workflows,
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
- PyreWire 1.0.0 is validated against wirelog v0.50.0 at peeled SHA
  `272edf3a24b25676f12c4b843d55510f5048dd2f`; the minimum compatible
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
  they require wirelog#852 and a runtime wirelog `0.44.0` or newer.
  The later [1.0.0] release is validated against and bundles wirelog
  v0.50.0.
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
  wirelog#852. They are available in the later [1.0.0] line, whose
  validated wirelog ref is v0.50.0. Tracked in wirelog#859.

[Unreleased]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.5...HEAD
[1.0.5]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/semantic-reasoning/PyreWire/compare/v0.41.0...v1.0.0
[0.41.0]: https://github.com/semantic-reasoning/PyreWire/releases/tag/v0.41.0
