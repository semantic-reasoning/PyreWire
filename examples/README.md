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
| `04_hash_functions.py` | wirelog 04 | Built-in `hash()` for email-fingerprint deduplication |
| `06_timestamp_lww.py` | wirelog 06 | Last-writer-wins via the `max()` aggregate |
| `07_multi_source_analysis.py` | wirelog 07 | Joining customer records from two sources with A-wins merge, conflict detection, and `count()` aggregation |
| `08_delta_queries.py` | wirelog 08 | Driving `EasySession.step()` and collecting per-step deltas |
| `10_recursive_under_update.py` | wirelog 10 | Incremental maintenance of a recursive rule under insert/remove/re-insert |
| `11_time_evolution.py` | wirelog 11 | Per-epoch delta isolation: each `step()` is a discrete time slice |
| `12_batch_vs_session.py` | wirelog 12 (in spirit) | Compares the batch closure path with the session's EDB preview |
| `12_snapshot_vs_delta.py` | wirelog 12 | Side-by-side comparison of `snapshot()` vs `step()` deliveries |
| `retraction_basics.py` | wirelog 09 | Symmetric retraction through `step()` |

## Deferred examples

`wirelog/examples/05-crc32-checksum` cannot be ported yet: wirelog
ships the `crc32_ethernet` / `crc32_castagnoli` enums in its IR
(`WIRELOG_ARITH_CRC32_ETH`, `WIRELOG_ARITH_CRC32_CAST`) and engine
(`wirelog/crc32.c`), but the **parser does not recognise them as
input keywords** — the lexer has tokens for `hash` / `md5` / `sha1` /
`sha256` / `sha512` / `hmac_sha256` / `uuid4` / `uuid5` but no
`crc32_*`. Running `wirelog_cli` on wirelog's own
`examples/05-crc32-checksum/crc32_validate.dl` against the v0.43.0
shared library returns `Parse error`. This port will land once
upstream wirelog wires `crc32_ethernet` / `crc32_castagnoli` into
the lexer.

The CSV-input examples (`02` style with external `.input`) require
the IO-adapter glue. `pyrewire.io_adapter.register_adapter` is
already shipped (#27); a CSV-adapter helper example will land
alongside the documentation page for it.
