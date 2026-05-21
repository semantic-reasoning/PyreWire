"""Wheel-bundled shared libraries live in this directory.

Populated by `auditwheel` / `delocate` / `delvewheel` during the wheel
build (`pip install pyrewire`). PyreWire's loader
(`pyrewire._ffi._loader`) prefers any `libwirelog` it finds here ahead
of the system loader. Source distributions intentionally ship this
package empty — the wirelog binary is never bundled into an sdist.
"""
