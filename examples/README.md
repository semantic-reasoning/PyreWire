# PyreWire examples

These scripts mirror the wirelog `examples/` programs, ported to
PyreWire's high-level API. Every example is runnable directly
(`python examples/<file>.py`) and is exercised by an integration
test under `tests/integration/test_examples.py`.

| File | Mirrors | What it shows |
| --- | --- | --- |
| `01_simple.py` | wirelog 01 | Inline facts + a single recursive rule, materialised via `BatchProgram.evaluate()` |
| `02_reachability.py` | wirelog 02 | Transitive closure over a directed graph |
| `03_bitwise.py` | wirelog 03 | Built-in `band` / `bor` / `bxor` / `bshl` / `bshr` |
| `06_timestamp_lww.py` | wirelog 06 | Last-writer-wins via the `max()` aggregate |
| `12_batch_vs_session.py` | wirelog 12 (in spirit) | Compares the batch closure path with the session's EDB preview |

## Deferred examples

The wirelog examples that drive `set_delta_callback` / incremental
`step()` (`08-delta-queries`, `10-recursive-under-update`,
`11-time-evolution`, and the original `12-snapshot-vs-delta`) require
`EasySession.step` / `snapshot`. Those wrappers ship once wirelog
cuts a release tag that includes
[wirelog#852](https://github.com/semantic-reasoning/wirelog/pull/852)
(tracked in
[wirelog#859](https://github.com/semantic-reasoning/wirelog/issues/859)).
The equivalent ports will land in the same PR that lands the
EasySession.step support.

The CSV-input examples (`02` style with external `.input`) require
the IO-adapter glue. `pyrewire.io_adapter.register_adapter` is
already shipped (#27); a CSV-adapter helper example will land
alongside the documentation page for it.
