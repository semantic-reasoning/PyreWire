# PyreWire

**Linting Status:**
| Tool | Status |
|------|--------|
| Black | [![Black](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml/badge.svg?job=black)](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml) |
| isort | [![isort](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml/badge.svg?job=isort)](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml) |
| Flake8 | [![Flake8](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml/badge.svg?job=flake8)](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml) |
| mypy | [![mypy](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml/badge.svg?job=mypy)](https://github.com/semantic-reasoning/PyreWire/actions/workflows/lint-push-main.yml) |

A Python wrapper for [wirelog](https://github.com/semantic-reasoning/wirelog) - a declarative dataflow analysis engine.

## Overview

PyreWire provides a Pythonic interface to wirelog, enabling you to write datalog programs and perform analysis programmatically from Python.

## Installation

```bash
pip install pyrewire
```

**Requirements:** Python 3.10 or later

## Quick Start

```python
from pyrewire import Program

# Create a new program
program = Program()

# Define relations
program.declare_relation("edge", [("x", "int32"), ("y", "int32")])
program.declare_relation("reach", [("x", "int32")])

# Add facts
program.add_fact("edge", [1, 2])
program.add_fact("edge", [2, 3])

# Add rules
program.add_rule("reach(1).")
program.add_rule("reach(Y) :- reach(X), edge(X, Y).")

# Execute
results = program.evaluate()
print(results.get_relation("reach"))
```

## Features

- 🎯 Easy-to-use Python API
- 📊 Support for declarative dataflow analysis
- ⚡ Efficient evaluation engine via wirelog
- 🔄 Integration with Python data structures

## Development

### Setup

```bash
git clone https://github.com/semantic-reasoning/PyreWire
cd pyrewire
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
