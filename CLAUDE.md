# PyreWire - Python wrapper for wirelog

Python FFI bindings for [wirelog](https://github.com/semantic-reasoning/wirelog), a declarative dataflow analysis engine.

- **wirelog** (`../wirelog`): C11 engine library (LGPL-3.0, Meson build) — what PyreWire wraps
- **wyrelog** (`../wyrelog`): application server using wirelog (GPL-3.0-or-later, C17, GLib/DuckDB) — unrelated to PyreWire

**License:** Apache-2.0 OR GPL-3.0-or-later (dual-licensed)

## Development

```bash
pip install -e ".[dev]"   # setup
pytest                     # test (coverage enabled by default)
black . && isort .         # format
flake8 . && mypy .         # lint
```

## Conventions

- **TDD:** Write tests first, then implementation
- **Atomic commits:** Each commit logically independent; include tests with implementation
- **No emojis** in commit messages
- **Google-style docstrings** for public APIs
- **Type hints** on all public APIs (Python 3.10+)

## FFI Design

- All C bindings go in `pyrewire/ffi.py` (ctypes/cffi)
- wirelog is a C11 library (Meson build); load the shared library at runtime

## Custom Agents

@AGENTS.md
