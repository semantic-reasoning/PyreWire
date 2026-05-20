"""Internal FFI layer for PyreWire.

This package is private to PyreWire (note the leading underscore). User code
must not import from `pyrewire._ffi` directly; use the public API exported
from the top-level `pyrewire` package instead.

Internal PyreWire modules use relative imports (e.g. `from ._ffi import LIB`)
rather than the absolute path so the `pyrewire._ffi` literal does not appear
outside this package.
"""

from ._loader import LIB

__all__ = ["LIB"]
