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
| `08_delta_queries.py` | wirelog 08 | Driving `EasySession.step()` and collecting per-step deltas |
| `10_recursive_under_update.py` | wirelog 10 | Incremental maintenance of a recursive rule under insert/remove/re-insert |
| `11_time_evolution.py` | wirelog 11 | Per-epoch delta isolation: each `step()` is a discrete time slice |
| `12_batch_vs_session.py` | wirelog 12 (in spirit) | Compares the batch closure path with the session's EDB preview |
| `12_snapshot_vs_delta.py` | wirelog 12 | Side-by-side comparison of `snapshot()` vs `step()` deliveries |
| `retraction_basics.py` | wirelog 09 | Symmetric retraction through `step()` |

## Deferred examples

The CSV-input examples (`02` style with external `.input`) require
the IO-adapter glue. `pyrewire.io_adapter.register_adapter` is
already shipped (#27); a CSV-adapter helper example will land
alongside the documentation page for it.
