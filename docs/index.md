# PyreWire

Python bindings for the
[wirelog](https://github.com/semantic-reasoning/wirelog) declarative
dataflow engine.

PyreWire wraps wirelog's public C API through `ctypes`, exposing four
high-level surfaces:

- **`EasySession`** — interactive `insert` / `remove` / (forthcoming
  `step` / `snapshot`) with automatic string interning. Best for
  ad-hoc experimentation and small workloads.
- **`Session`** — the advanced API. Caller-owned `Program`, backend
  selection, batched zero-copy NumPy inserts, explicit mode machine.
- **`BatchProgram`** + **`Result`** — `optimize → evaluate → CSV` for
  one-shot IDB closure computation.
- **`AsyncEasySession`** / **`AsyncSession`** / **`AsyncBatchProgram`**
  — asyncio proxies that run every call on a dedicated single-worker
  thread, satisfying wirelog's "no concurrent calls" invariant.

## Install

```bash
pip install pyrewire
```

The wheel bundles `libwirelog`; no system install required.

## Where to next

- [Quickstart](quickstart.md) — a six-line example you can paste.
- [Versioning](versioning.md) — PyreWire's release cadence is tied to
  wirelog's.
- [Reference](reference/sessions.md) — auto-generated from the
  public-API docstrings.
