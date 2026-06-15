# Errors

Every fallible wirelog C entry point returns a `wirelog_error_t` integer code.
The [`check()`][pyrewire._core.errors.check] helper maps any non-OK code to the
matching typed Python exception, so callers can write
`except CompoundBusyError:` instead of inspecting raw integers.
PyreWire adds three loader/session/intern-level errors —
[`WirelogVersionError`][pyrewire._core.errors.WirelogVersionError],
[`WirelogModeError`][pyrewire._core.errors.WirelogModeError], and
[`WirelogInternError`][pyrewire._core.errors.WirelogInternError] —
that have no C counterpart and are never produced by `check()`.

## Error-code mapping

| `wirelog_error_t` | Code | `error_string` text | Exception class |
|---|---|---|---|
| `WIRELOG_OK` | 0 | ok | — (`check()` returns `None`) |
| `WIRELOG_ERR_PARSE` | 1 | parse error | [`ParseError`][pyrewire._core.errors.ParseError] |
| `WIRELOG_ERR_INVALID_IR` | 2 | invalid IR | [`InvalidIRError`][pyrewire._core.errors.InvalidIRError] |
| `WIRELOG_ERR_EXEC` | 3 | execution error | [`ExecError`][pyrewire._core.errors.ExecError] |
| `WIRELOG_ERR_MEMORY` | 4 | out of memory | [`WirelogMemoryError`][pyrewire._core.errors.WirelogMemoryError] |
| `WIRELOG_ERR_IO` | 5 | I/O error | [`WirelogIOError`][pyrewire._core.errors.WirelogIOError] |
| `WIRELOG_ERR_COMPOUND_SATURATED` | 6 | compound arena saturated | [`CompoundSaturatedError`][pyrewire._core.errors.CompoundSaturatedError] |
| `WIRELOG_ERR_COMPOUND_BUSY` | 7 | compound arena busy | [`CompoundBusyError`][pyrewire._core.errors.CompoundBusyError] |
| (any other non-zero) | 255 | unknown error | [`WirelogError`][pyrewire._core.errors.WirelogError] (base) |

Codes with no specific class (including `WIRELOG_ERR_UNKNOWN`/255) raise the
base [`WirelogError`][pyrewire._core.errors.WirelogError] via `check()`'s
fallback.

### PyreWire-only errors (not produced by `check()`)

- [`WirelogVersionError`][pyrewire._core.errors.WirelogVersionError] — raised
  when the loaded libwirelog is missing an optional capability or symbol
  required by a PyreWire API.
- [`WirelogModeError`][pyrewire._core.errors.WirelogModeError] — raised by
  session classes when an operation is attempted in the wrong session mode
  (step/snapshot/query); the session must be closed and reopened to switch
  modes.
- [`WirelogInternError`][pyrewire._core.errors.WirelogInternError] — raised
  when a symbol-id reverse lookup fails.

## Exception handling

```python
from pyrewire import ParseError, Program
from pyrewire import CompoundBusyError  # see docs/semantics/compounds.md for retry loop

try:
    prog = Program.from_file("rules.wl")
except ParseError as exc:
    # line and column are populated for file-based parsing
    loc = f"{exc.source}:{exc.line}:{exc.column}" if exc.line else str(exc.source)
    print(f"Parse failed at {loc}: {exc}")
```

[`CompoundBusyError`][pyrewire._core.errors.CompoundBusyError] is a transient arena-contention error that should be retried with backoff — see the [retry loop in the Compounds semantics guide](../semantics/compounds.md#retry-loop-for-compoundbusyerror).

## API reference

`error_string()` prefers the live `wirelog_error_string` symbol when available
and falls back to a PyreWire-side text table on older builds, so its output may
differ slightly from the table above (e.g. `OK` vs `ok`).

::: pyrewire._core.errors.check

::: pyrewire._core.errors.error_string

## Exception classes

::: pyrewire._core.errors.WirelogError

::: pyrewire._core.errors.ParseError

::: pyrewire._core.errors.InvalidIRError

::: pyrewire._core.errors.ExecError

::: pyrewire._core.errors.WirelogMemoryError

::: pyrewire._core.errors.WirelogIOError

::: pyrewire._core.errors.CompoundSaturatedError

::: pyrewire._core.errors.CompoundBusyError

::: pyrewire._core.errors.WirelogVersionError

::: pyrewire._core.errors.WirelogModeError

::: pyrewire._core.errors.WirelogInternError
