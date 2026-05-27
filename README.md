# PyreWire

[![CI](https://github.com/semantic-reasoning/PyreWire/actions/workflows/ci.yml/badge.svg)](https://github.com/semantic-reasoning/PyreWire/actions/workflows/ci.yml)
[![Docs](https://github.com/semantic-reasoning/PyreWire/actions/workflows/docs.yml/badge.svg)](https://github.com/semantic-reasoning/PyreWire/actions/workflows/docs.yml)

The `ci` workflow runs the full lint gate (black, isort, flake8, mypy)
and the test matrix; `docs` builds and publishes the documentation site.

A Python wrapper for [wirelog](https://github.com/semantic-reasoning/wirelog) - a declarative dataflow analysis engine.

## Overview

PyreWire provides a Pythonic interface to wirelog, enabling you to write datalog programs and perform analysis programmatically from Python.

## Installation

```bash
pip install pyrewire
```

**Requirements:** Python 3.11 or later

## Quick Start

PyreWire programs are written in wirelog's datalog dialect and driven
through one of the high-level surfaces below.

### One-shot evaluation with `BatchProgram`

Use `BatchProgram` to parse a program, optimize it, and compute the full
IDB closure in a single pass:

```python
from pyrewire import BatchProgram

# A tiny reachability program: two edges plus a transitive-closure rule.
src = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32, y: int32)
edge(1, 2). edge(2, 3).
reach(X, Y) :- edge(X, Y).
reach(X, Z) :- reach(X, Y), edge(Y, Z).
"""

with BatchProgram.from_string(src) as program:
    program.optimize()
    result = program.evaluate()
    try:
        print(result.cardinality("reach"))   # 3
        print(result.relation("reach"))      # [(1, 2), (2, 3), (1, 3)]
    finally:
        result.close()
```

### Incremental work with `EasySession`

`EasySession` interns strings automatically and lets you `insert` /
`remove` facts, then either `snapshot` a relation's full contents or
`step` the engine for incremental deltas. A session commits to a single
mode the first time you query it, so use a fresh session per mode:

```python
from pyrewire import EasySession

SRC = """
.decl friend(a: symbol, b: symbol)
.decl mutual(a: symbol, b: symbol)
mutual(A, B) :- friend(A, B), friend(B, A).
"""

# snapshot(): read a relation's full IDB contents.
with EasySession(SRC) as s:
    s.insert("friend", ["alice", "bob"])
    s.insert("friend", ["bob", "alice"])
    print(s.snapshot("mutual"))   # [('alice', 'bob'), ('bob', 'alice')]

# step(): drive one fixpoint step and read the incremental deltas.
with EasySession(SRC) as s:
    s.insert("friend", ["alice", "bob"])
    s.insert("friend", ["bob", "alice"])
    for relation, row, diff in s.step():
        print(relation, row, diff)   # e.g. mutual ('alice', 'bob') 1
```

For caller-owned programs, backend selection, and NumPy zero-copy
inserts, see `Session`; for asyncio integration see `AsyncEasySession`,
`AsyncSession`, and `AsyncBatchProgram`. The
[Quickstart](docs/quickstart.md) walks through each surface.

## Features

- Pythonic API over wirelog's declarative dataflow engine
- Batch closure (`BatchProgram`) and incremental sessions (`EasySession`, `Session`)
- NumPy zero-copy batched inserts on the advanced `Session` API
- asyncio wrappers that satisfy wirelog's single-threaded call invariant

## Development

### Setup

```bash
git clone https://github.com/semantic-reasoning/PyreWire
cd PyreWire
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
black .
isort .
flake8 .
mypy .
```

## Community & Contributing

We appreciate your interest in contributing to PyreWire!

- **[Contributing Guide](./CONTRIBUTING.md)**: Learn how to set up development, run tests, and submit pull requests
- **[Code of Conduct](./CODE_OF_CONDUCT.md)**: Read our community standards and expected behavior
- **[Security Policy](./SECURITY.md)**: Report security vulnerabilities responsibly

## License

**PyreWire (Python Wrapper):** dual-licensed under either of

- [Apache License, Version 2.0](LICENSE-APACHE)
- [GNU General Public License, version 3 or (at your option) any later version](LICENSE-GPL)

at your option.

**wirelog (Core Engine):** LGPL-3.0 / Commercial Dual License

**Note:** PyreWire links to the wirelog core engine. Use of the core engine is subject to its respective license terms.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
