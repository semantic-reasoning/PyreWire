"""Wrappers for wirelog utility entry points (version, error_string,
config probes, enum-to-string converters).

Each symbol is resolved lazily through `_try_resolve(name, restype, args)`.
If the symbol is exported (the default since semantic-reasoning/wirelog#841)
the wrapper calls into libwirelog directly; if not, a PyreWire-side
fallback table or `None` keeps user code from crashing. The fallback
paths are kept indefinitely as a forward-compatibility net for users
paired with pre-#841 libwirelog builds.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import Any

from . import LIB
from ._enums import AggFn, ArithOp, CmpOp

# --- Internal: lazy single-symbol resolver ---------------------------------


def _try_resolve(
    name: str,
    restype: Any,
    argtypes: list[Any],
) -> Callable[..., Any] | None:
    """Resolve `LIB.<name>` if exported; return a configured callable or None."""
    try:
        fn = getattr(LIB, name)
    except AttributeError:
        return None
    fn.restype = restype
    fn.argtypes = argtypes
    return fn  # type: ignore[no-any-return]


_version_fn = _try_resolve("wirelog_version_string", ctypes.c_char_p, [])
_cmp_str_fn = _try_resolve("wirelog_cmp_op_str", ctypes.c_char_p, [ctypes.c_int])
_arith_str_fn = _try_resolve("wirelog_arith_op_str", ctypes.c_char_p, [ctypes.c_int])
_agg_str_fn = _try_resolve("wirelog_agg_fn_str", ctypes.c_char_p, [ctypes.c_int])
_config_embedded_fn = _try_resolve("wirelog_config_embedded", ctypes.c_bool, [])
_config_ipc_fn = _try_resolve("wirelog_config_ipc", ctypes.c_bool, [])
_config_threads_fn = _try_resolve("wirelog_config_threads", ctypes.c_bool, [])


# --- Public helpers --------------------------------------------------------


def wirelog_version() -> str:
    """Return the loaded libwirelog's version string.

    Prefers `LIB.wirelog_version_string()`. Falls back to
    `pyrewire.__version__` (PEP 440 local-version segment stripped) only
    against pre-#841 builds without the symbol; PyreWire's versioning
    rule keeps the two in lock-step so the fallback is informationally
    equivalent.
    """
    if _version_fn is not None:
        raw = _version_fn()
        if raw:
            return raw.decode("utf-8", errors="replace")  # type: ignore[no-any-return]
    # Pre-#841 fallback: cannot ask the library; report what pyrewire is
    # pinned to. The loader has already confirmed library presence via
    # the sentinel-symbol probe.
    from .. import __version__  # local import to avoid early circular load
    from ._loader import _pep440_base

    return _pep440_base(__version__)


def build_config() -> dict[str, bool | None]:
    """Return wirelog build-config flags.

    Returns `{'embedded': bool|None, 'ipc': bool|None, 'threads': bool|None}`.
    `None` for a flag means the corresponding `wirelog_config_*` probe is
    not exported (pre-#841 build); callers should treat `None` as
    'no information', not as `False`.
    """
    return {
        "embedded": bool(_config_embedded_fn()) if _config_embedded_fn else None,
        "ipc": bool(_config_ipc_fn()) if _config_ipc_fn else None,
        "threads": bool(_config_threads_fn()) if _config_threads_fn else None,
    }


def cmp_op_name(op: CmpOp | int) -> str:
    """Return the canonical wirelog text for a comparison operator."""
    if _cmp_str_fn is None:
        return _CMP_FALLBACK.get(int(op), f"cmp_op({int(op)})")
    raw = _cmp_str_fn(int(op))
    return raw.decode() if raw else _CMP_FALLBACK.get(int(op), f"cmp_op({int(op)})")


def arith_op_name(op: ArithOp | int) -> str:
    """Return the canonical wirelog text for an arithmetic / function operator."""
    if _arith_str_fn is None:
        return _ARITH_FALLBACK.get(int(op), f"arith_op({int(op)})")
    raw = _arith_str_fn(int(op))
    return raw.decode() if raw else _ARITH_FALLBACK.get(int(op), f"arith_op({int(op)})")


def agg_fn_name(fn: AggFn | int) -> str:
    """Return the canonical wirelog text for an aggregate function."""
    if _agg_str_fn is None:
        return _AGG_FALLBACK.get(int(fn), f"agg_fn({int(fn)})")
    raw = _agg_str_fn(int(fn))
    return raw.decode() if raw else _AGG_FALLBACK.get(int(fn), f"agg_fn({int(fn)})")


# --- Fallbacks used when the symbol is unavailable -------------------------
# These exist only as a last-resort safety net; the live wirelog values
# always take precedence when the symbol resolves.

_CMP_FALLBACK = {
    int(CmpOp.EQ): "=",
    int(CmpOp.NEQ): "!=",
    int(CmpOp.LT): "<",
    int(CmpOp.GT): ">",
    int(CmpOp.LTE): "<=",
    int(CmpOp.GTE): ">=",
}

_ARITH_FALLBACK = {
    int(ArithOp.ADD): "+",
    int(ArithOp.SUB): "-",
    int(ArithOp.MUL): "*",
    int(ArithOp.DIV): "/",
    int(ArithOp.MOD): "%",
    int(ArithOp.BAND): "band",
    int(ArithOp.BOR): "bor",
    int(ArithOp.BXOR): "bxor",
    int(ArithOp.BNOT): "bnot",
    int(ArithOp.SHL): "bshl",
    int(ArithOp.SHR): "bshr",
    int(ArithOp.HASH): "hash",
    int(ArithOp.CRC32_ETH): "crc32_ethernet",
    int(ArithOp.CRC32_CAST): "crc32_castagnoli",
    int(ArithOp.MD5): "md5",
    int(ArithOp.SHA1): "sha1",
    int(ArithOp.SHA256): "sha256",
    int(ArithOp.SHA512): "sha512",
    int(ArithOp.HMAC_SHA256): "hmac_sha256",
    int(ArithOp.UUID4): "uuid4",
    int(ArithOp.UUID5): "uuid5",
}

_AGG_FALLBACK = {
    int(AggFn.COUNT): "count",
    int(AggFn.SUM): "sum",
    int(AggFn.MIN): "min",
    int(AggFn.MAX): "max",
    int(AggFn.AVG): "average",
}


__all__ = [
    "wirelog_version",
    "build_config",
    "cmp_op_name",
    "arith_op_name",
    "agg_fn_name",
]
