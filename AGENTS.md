# PyreWire Project Agents

Custom agent specializations for PyreWire (Python wrapper for wirelog).

## ffi-specialist

**Purpose:** Handle Python/C FFI bindings and wirelog integration
**Capabilities:**
- ctypes/cffi configuration
- C library binding validation
- Memory management patterns
- Cross-platform C library loading

**When to use:**
- Implementing wirelog C function wrapping
- Debugging FFI call failures
- Performance optimization of C boundary crossings

## datalog-expert

**Purpose:** Datalog syntax, semantics, and query optimization
**Capabilities:**
- wirelog syntax validation
- Rule/fact correctness checking
- Query plan analysis
- Performance optimization for datalog programs

**When to use:**
- Validating user program syntax
- Optimizing generated datalog rules
- Explaining datalog behavior to users

## python-pkg-specialist

**Purpose:** Python packaging, distribution, and compatibility
**Capabilities:**
- pyproject.toml configuration
- Cross-version compatibility testing (3.8+)
- Packaging/publishing workflows
- Dependency management

**When to use:**
- Building distribution artifacts
- Version compatibility issues
- Publishing to PyPI
- Dependency resolution conflicts

## bindings-validator

**Purpose:** Validate C bindings and FFI correctness
**Capabilities:**
- FFI signature validation
- Memory safety checks
- Type consistency verification
- Integration testing

**When to use:**
- After adding new C function wrappers
- Before releases
- Debugging segfaults or memory issues
