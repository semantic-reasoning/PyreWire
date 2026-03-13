# PyreWire

A Python wrapper for [Wirelog](https://github.com/justinjoy/wirelog) - a declarative dataflow analysis engine.

## Overview

PyreWire provides a Pythonic interface to Wirelog, enabling you to write datalog programs and perform analysis programmatically from Python.

## Installation

```bash
pip install pyrewire
```

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
- ⚡ Efficient evaluation engine via Wirelog
- 🔄 Integration with Python data structures

## Development

### Setup

```bash
git clone https://github.com/gazgiz/PyreWire
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

## License

PyreWire is dual-licensed under either of

- [Apache License, Version 2.0](LICENSE-APACHE)
- [GNU General Public License, version 3 or (at your option) any later version](LICENSE-GPL)

at your option.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
