<!-- OMC:START -->

# PyreWire - Python Wrapper for Wirelog

PyreWire is a Python wrapper providing Pythonic interfaces to [Wirelog](https://github.com/justinjoy/wirelog), a declarative dataflow analysis engine.

**Dual-licensed: Apache-2.0 OR GPL-3.0-or-later** | **Project Skeleton: Established 2026-03-13**

## Project Goals

1. **Python FFI Bindings:** Safe, ergonomic ctypes/cffi wrappers around Wirelog C library
2. **User-Friendly API:** Hide complexity of datalog programs behind intuitive Python classes
3. **Broad Python Support:** Target Python 3.8+ for wide adoption
4. **Comprehensive Testing:** Unit, integration, and FFI validation tests

## Architecture

```
src/pyrewire/
  ├── __init__.py       # Public API exports
  ├── program.py        # Program class (datalog builder)
  ├── result.py         # Result handling (query outputs)
  ├── ffi.py            # Wirelog C bindings (TODO)
  └── errors.py         # Custom exceptions (TODO)

tests/
  ├── test_program.py   # Program API tests
  ├── test_ffi.py       # FFI binding validation (TODO)
  └── test_integration.py # End-to-end tests (TODO)
```

## Development Workflow

### Setup
```bash
pip install -e ".[dev]"
```

### Testing
```bash
pytest --cov=pyrewire
```

### Code Quality
```bash
black . && isort . && flake8 . && mypy .
```

### Key Guidelines

1. **FFI Bindings:** All Wirelog C function wrappers live in `pyrewire/ffi.py`
2. **Type Hints:** Use type annotations for all public APIs (Python 3.8+ compatible)
3. **Docstrings:** Google-style docstrings for all classes/functions
4. **Testing:** Aim for 80%+ coverage; FFI tests must validate C boundary
5. **Backwards Compatibility:** Once released, maintain semver compatibility

## Custom Agents

@AGENTS.md

---

## Dependencies

- **Runtime:** None (pure Python + C library)
- **Dev:** pytest, black, isort, flake8, mypy

## License

Dual-licensed under **Apache-2.0 OR GPL-3.0-or-later** — see `LICENSE`, `LICENSE-APACHE`, and `LICENSE-GPL`.

<!-- OMC:END -->
