# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""`@register_adapter` decorator for wirelog IO adapters (#27).

Lets Python classes serve as the source for `.input Rel(IO="scheme", …)`
directives. The decorator builds a `wirelog_io_adapter_t`, wraps the
user's `read` / `validate` methods in ctypes trampolines, registers the
adapter with wirelog, and keeps every piece of state alive for the
lifetime of the registration (the C side holds pointers; if Python GCs
the trampolines or scheme bytes wirelog calls into freed memory).

The read callback must hand wirelog a malloc'd `int64_t *` buffer
(wirelog calls `free` on it after consuming). PyreWire uses the
shared `libc_malloc` helper so the allocator matches.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from ._core._libc import libc_malloc
from ._core.errors import WirelogIOError
from ._ffi import LIB
from ._ffi import _io as _io_ffi  # noqa: F401  -- registers argtypes
from ._ffi._enums import ColumnType
from ._ffi._types import (
    WIRELOG_IO_ABI_VERSION,
    IOAdapterStruct,
    IOCtxHandle,
)


class IOContext:
    """Thin Python wrapper over a `wirelog_io_ctx_t *` for use inside
    adapter callbacks."""

    __slots__ = ("_ctx",)

    def __init__(self, ctx: IOCtxHandle) -> None:
        self._ctx = ctx

    @property
    def relation_name(self) -> str:
        s = LIB.wirelog_io_ctx_relation_name(self._ctx)
        return s.decode("utf-8", errors="replace") if s else ""

    @property
    def num_cols(self) -> int:
        return int(LIB.wirelog_io_ctx_num_cols(self._ctx))

    def col_type(self, col: int) -> ColumnType:
        return ColumnType(int(LIB.wirelog_io_ctx_col_type(self._ctx, ctypes.c_uint32(col))))

    def param(self, key: str) -> str | None:
        s = LIB.wirelog_io_ctx_param(self._ctx, key.encode("utf-8"))
        return s.decode("utf-8", errors="replace") if s else None

    def intern_string(self, value: str) -> int:
        return int(LIB.wirelog_io_ctx_intern_string(self._ctx, value.encode("utf-8")))


@runtime_checkable
class Adapter(Protocol):
    def read(self, ctx: IOContext) -> list[list[int]]: ...


class _Registration:
    """Holds every piece of state wirelog still references after a
    successful `wirelog_io_register_adapter`. Must outlive the call to
    `wirelog_io_unregister_adapter`."""

    __slots__ = (
        "scheme_bytes",
        "description_bytes",
        "adapter_struct",
        "read_cfunc",
        "validate_cfunc",
        "py_instance",
    )

    def __init__(
        self,
        scheme_bytes: bytes,
        description_bytes: bytes,
        adapter_struct: IOAdapterStruct,
        read_cfunc: Any,
        validate_cfunc: Any,
        py_instance: Any,
    ) -> None:
        self.scheme_bytes = scheme_bytes
        self.description_bytes = description_bytes
        self.adapter_struct = adapter_struct
        self.read_cfunc = read_cfunc
        self.validate_cfunc = validate_cfunc
        self.py_instance = py_instance


_REGISTRY: dict[str, _Registration] = {}
_REGISTRY_LOCK = threading.Lock()


def _read_field_cfunctype() -> Any:
    return IOAdapterStruct._fields_[3][1]


def _validate_field_cfunctype() -> Any:
    return IOAdapterStruct._fields_[4][1]


def _build_read_cfunc(py_instance: Any) -> Any:
    read_t = _read_field_cfunctype()

    @read_t  # type: ignore[untyped-decorator]
    def _read(
        ctx: Any,
        out_data: Any,
        out_nrows: Any,
        _user_data: Any,
    ) -> int:
        try:
            rows = py_instance.read(IOContext(ctx))
        except BaseException:
            return -1
        if not rows:
            out_nrows[0] = 0
            out_data[0] = ctypes.cast(0, ctypes.POINTER(ctypes.c_int64))
            return 0
        ncols = int(LIB.wirelog_io_ctx_num_cols(ctx))
        n = len(rows)
        total_bytes = n * ncols * ctypes.sizeof(ctypes.c_int64)
        buf_addr = libc_malloc(total_bytes)
        if not buf_addr:
            return -1
        as_i64 = ctypes.cast(buf_addr, ctypes.POINTER(ctypes.c_int64))
        for i, row in enumerate(rows):
            if len(row) != ncols:
                return -1
            for j, v in enumerate(row):
                as_i64[i * ncols + j] = int(v)
        out_data[0] = as_i64
        out_nrows[0] = n
        return 0

    return _read


def _build_validate_cfunc(py_instance: Any) -> Any:
    validate_t = _validate_field_cfunctype()
    user_validate = getattr(py_instance, "validate", None)

    if user_validate is None:

        @validate_t  # type: ignore[untyped-decorator]
        def _noop(_ctx: Any, _errbuf: Any, _errbuf_len: Any, _user_data: Any) -> int:
            return 0

        return _noop

    @validate_t  # type: ignore[untyped-decorator]
    def _validate(ctx: Any, errbuf: Any, errbuf_len: Any, _user_data: Any) -> int:
        try:
            user_validate(IOContext(ctx))
            return 0
        except BaseException as exc:
            try:
                msg = str(exc).encode("utf-8")
                n = min(len(msg), max(0, int(errbuf_len) - 1))
                if n and errbuf:
                    ctypes.memmove(errbuf, msg[:n], n)
                    ctypes.cast(errbuf, ctypes.POINTER(ctypes.c_char))[n] = b"\x00"
            except Exception:
                pass
            return -1

    return _validate


def register_adapter(scheme: str, description: str = "") -> Callable[[type], type]:
    """Decorator: register a class as an adapter for `scheme`.

    The class is instantiated once and reused for every wirelog
    callback. Provide a `read(ctx) -> list[list[int]]` method and,
    optionally, a `validate(ctx) -> None` method that raises on bad
    input.
    """
    if not scheme:
        raise ValueError("scheme must be non-empty")

    def deco(cls: type) -> type:
        instance = cls()
        scheme_b = scheme.encode("utf-8")
        desc_b = description.encode("utf-8")
        read_fn = _build_read_cfunc(instance)
        val_fn = _build_validate_cfunc(instance)
        adapter = IOAdapterStruct(
            abi_version=WIRELOG_IO_ABI_VERSION,
            scheme=scheme_b,
            description=desc_b,
            read=read_fn,
            validate=val_fn,
            user_data=None,
        )
        rc = LIB.wirelog_io_register_adapter(ctypes.byref(adapter))
        if rc != 0:
            err = LIB.wirelog_io_last_error()
            raise WirelogIOError(
                f"wirelog_io_register_adapter failed for {scheme!r}: "
                f"{err.decode('utf-8', errors='replace') if err else 'unknown error'}"
            )
        with _REGISTRY_LOCK:
            # If a previous registration leaked, drop its keep-alive only
            # after wirelog acknowledges the new one.
            _REGISTRY[scheme] = _Registration(scheme_b, desc_b, adapter, read_fn, val_fn, instance)
        return cls

    return deco


def unregister_adapter(scheme: str) -> None:
    """Release a previously-registered adapter. No-op if `scheme` is
    not in the registry."""
    with _REGISTRY_LOCK:
        if scheme not in _REGISTRY:
            return
        rc = LIB.wirelog_io_unregister_adapter(scheme.encode("utf-8"))
        if rc != 0:
            err = LIB.wirelog_io_last_error()
            raise WirelogIOError(
                f"wirelog_io_unregister_adapter failed for {scheme!r}: "
                f"{err.decode('utf-8', errors='replace') if err else 'unknown error'}"
            )
        del _REGISTRY[scheme]


def registered_schemes() -> list[str]:
    """Snapshot of currently-registered schemes (for tests / debugging)."""
    with _REGISTRY_LOCK:
        return list(_REGISTRY.keys())


__all__ = [
    "IOContext",
    "Adapter",
    "register_adapter",
    "unregister_adapter",
    "registered_schemes",
]
