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
| `04_hash_functions.py` | wirelog 04 | Built-in `hash()` for email-fingerprint deduplication and stored-checksum validation |
| `05_crc32_checksum.py` | wirelog 05 | Built-in `crc32_ethernet()` for frame checksum validation |
| `06_timestamp_lww.py` | wirelog 06 | Last-writer-wins via the `max()` aggregate |
| `07_multi_source_analysis.py` | wirelog 07 | Joining customer records from two sources with A-wins merge, conflict detection, and `count()` aggregation |
| `08_delta_queries.py` | wirelog 08 | Driving `EasySession.step()` and collecting per-step deltas |
| `10_recursive_under_update.py` | wirelog 10 | Incremental maintenance of a recursive rule under insert/remove/re-insert |
| `11_time_evolution.py` | wirelog 11 | Per-epoch delta isolation: each `step()` is a discrete time slice |
| `12_batch_vs_session.py` | wirelog 12 (in spirit) | Compares the batch closure path with the session's EDB preview |
| `12_snapshot_vs_delta.py` | wirelog 12 | Side-by-side comparison of `snapshot()` vs `step()` deliveries |
| `csv_adapter_reachability.py` | PyreWire IO adapter | Supplies `.input` facts through `register_adapter` and `load_input_files()` |
| `retraction_basics.py` | wirelog 09 | Symmetric retraction through `step()` |
