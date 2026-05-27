# API stability

PyreWire v1.0 treats `pyrewire.__all__` as the stable public import boundary.
Names listed there are the supported surface for
`from pyrewire import ...` imports and are covered by the v1 API
compatibility and deprecation policy.

## Stable public boundary

The v1 stable public API includes these exported names:

### Sessions

- `EasySession`
- `Session`

### Batch and result

- `BatchProgram`
- `Result`

### Program, schema, and introspection

- `Program`
- `Schema`
- `Column`
- `Stratum`

### Async wrappers

- `AsyncEasySession`
- `AsyncSession`
- `AsyncBatchProgram`

### IO adapters

- `IOContext`
- `register_adapter`
- `unregister_adapter`
- `registered_schemes`

### Compounds

- `Compound`
- `CompoundArg`

### IR wrapper and enums

- `IRNode`
- `IRNodeType`

### Exported enums

- `ColumnType`
- `CompoundKind`
- `BackendKind`
- `CmpOp`
- `ArithOp`
- `AggFn`
- `StrFn`
- `ErrorCode`

### Exported errors

- `WirelogError`
- `ParseError`
- `InvalidIRError`
- `ExecError`
- `WirelogMemoryError`
- `WirelogIOError`
- `CompoundSaturatedError`
- `CompoundBusyError`
- `WirelogVersionError`
- `WirelogModeError`
- `WirelogInternError`

### Helpers and utilities

- `__version__`
- `Delta`
- `make_safe_print_delta`
- `is_wirelog_print_delta`
- `wirelog_version`
- `build_config`
- `cmp_op_name`
- `arith_op_name`
- `agg_fn_name`

## Non-public boundary

Everything outside `pyrewire.__all__` is non-public unless a later
stable policy explicitly promotes it. In particular, the following are
not stable public API:

- `pyrewire._ffi`
- `pyrewire._core`
- `pyrewire._lib`
- raw `ctypes` handles and structures
- private attributes, including names beginning with `_`
- non-exported internals in any PyreWire module

These internals may change, move, or disappear in any release.

## Deprecation policy

When PyreWire needs to change a stable v1 API incompatibly, it will emit
a `DeprecationWarning` where practical before removal or incompatible
behavior changes. Public API removals should warn for at least one minor release
before the incompatible removal.

Incompatible removals are reserved for major releases except urgent security or correctness cases.
If an urgent security or correctness fix
requires faster action, the release notes will call out the exception
and the affected API.

Minor releases may add compatible public API surface, including new APIs,
optional parameters, enum members, and exception subclasses. Code
that handles PyreWire enums or exception hierarchies should therefore
avoid assuming that the v1.0 set is permanently exhaustive.
