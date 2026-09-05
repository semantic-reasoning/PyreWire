# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Conversion between Python values and wirelog's 64-bit typed lanes.

wirelog's typed row ABI carries every column as a `uint64_t` lane plus a
`wirelog_column_type_t` saying how to read it. A FLOAT lane holds
host-order IEEE-754 binary64 bits rather than a C `double`, so a float
only survives the boundary through an explicit bit reinterpret - which is
exactly what the untyped `int64_t` entry points cannot do.

These helpers live here rather than on `Session` because both the typed
insert path (`pyrewire.session`) and the typed delta trampoline
(`pyrewire._core.callbacks`) need them, and the trampoline cannot import
the session module without a cycle.
"""

from __future__ import annotations

import ctypes
import numbers
import operator
import struct
from typing import Any, SupportsFloat, SupportsIndex

from .._ffi._enums import ColumnType

# What a single lane can hold once decoded. BOOL decodes to `bool`, which
# is an `int` subclass, so the union is a documentation aid rather than a
# discriminator.
LaneValue = int | float | bool

# What `encode_lane` accepts: anything integer-like or float-like. Wider
# than `LaneValue`, so a NumPy scalar or any `__index__` type goes in.
LaneInput = SupportsIndex | SupportsFloat

_FLOAT = struct.Struct("<d")
_BITS = struct.Struct("<Q")

_UINT64_MASK = 0xFFFFFFFFFFFFFFFF


def encode_lane(value: LaneInput, column_type: ColumnType) -> int:
    """Pack one Python value into its 64-bit lane.

    Integer columns take the value's two's-complement bits. A float that
    names an exact integer (`3.0`) is accepted there; a non-integral one
    is rejected rather than silently truncated.

    Anything implementing `__index__` or `__float__` is accepted, so a
    NumPy scalar works here as it does through `insert_batch`. `str` is
    the deliberate exclusion. A float-like value heading for an integer
    column is converted through `float`; if it is also a real numeric
    type, the result is checked against the original and refused when the
    conversion lost information - `Decimal(2**63 - 1)` names an integer a
    binary64 cannot hold, and is refused rather than stored one off.

    Raises:
        ValueError: a float-like value was given for an integer column and
            it does not name an exactly representable integer.
        TypeError: a `str`, or a value that is neither integer-like nor
            float-like, was given.
        OverflowError: the value is too large to convert to a float at
            all, as `10**400` is.
    """
    # Concrete types first. `isinstance` against a runtime-checkable
    # Protocol probes for attributes and has no negative-result cache, so
    # leaving it in front of the common case costs ~25% of a large typed
    # insert. `type(...) is` deliberately excludes bool, which falls
    # through to the __index__ path below and encodes as 0/1 either way.
    is_int = type(value) is int
    is_float = type(value) is float
    if not is_int and not is_float:
        if isinstance(value, str):
            raise TypeError(
                f"cannot encode str {value!r} into a lane: a STRING column carries an "
                f"intern id, and the advanced Session has no forward-intern API. Pass "
                f"the int64 id, seeding it with seed_intern(value, id) if you need to "
                f"decode it back."
            )
        if not isinstance(value, (SupportsIndex, SupportsFloat)):
            raise TypeError(f"cannot encode {type(value).__name__} {value!r} into a lane")

    if column_type == ColumnType.FLOAT:
        bits: int = _BITS.unpack(_FLOAT.pack(_as_float(value)))[0]
        return bits

    if is_int:
        return value & _UINT64_MASK  # type: ignore[operator]
    if not is_float and isinstance(value, SupportsIndex):
        # `operator.index` enforces that __index__ returned an int, where
        # calling the dunder directly would let a bogus return value reach
        # the `&` below as some other type.
        return operator.index(value) & _UINT64_MASK

    # Float-like heading for an integer column: accept it only when it
    # names an exact integer, and only when converting through float did
    # not already lose the value.
    as_float = _as_float(value)
    if not as_float.is_integer():
        raise ValueError(f"cannot store float {value!r} in a {ColumnType(column_type).name} column")
    as_int = int(as_float)
    if not is_float and _float_conversion_lost_value(value, as_int):
        raise ValueError(
            f"cannot store {type(value).__name__} {value!r} in a "
            f"{ColumnType(column_type).name} column: it is not exactly representable "
            f"as a 64-bit float, so the stored value would be {as_int}"
        )
    return as_int & _UINT64_MASK


def _float_conversion_lost_value(value: object, as_int: int) -> bool:
    """Whether routing `value` through `float` lost information.

    The check runs only for a type registered with `numbers.Number`.
    `Decimal` and `Fraction` carry an exact value that `float` may round
    - `Decimal(2**63 - 1)` becomes `2**63` - and they compare numerically
    against `int`, so for them the question is meaningful and the answer
    is trustworthy.

    Everything else is accepted without asking, because for most
    `__float__` providers the protocol is the only thing exposed:
    `float(value)` IS the value and nothing can have been lost. Asking
    anyway would compare an `int` against an object with no numeric
    `__eq__`, fall back to identity, and reject every such value while
    claiming it was unrepresentable - which is how this guard read
    before, and it was wrong.

    `numbers.Number` is a proxy for "can answer the question", not the
    thing itself, and it is imprecise in both directions: an exact
    numeric type that declines to register is not checked, and a
    non-numeric type that registers without defining `__eq__` is checked
    and wrongly refused. Gating on `type(value).__eq__` instead trades
    one of those for a worse one - a wrapper whose `__eq__` returns
    `False` rather than `NotImplemented` for an `int` goes back to being
    falsely rejected. The documented contract is therefore scoped to real
    numeric types rather than to this mechanism.

    A comparison that raises is treated as "cannot tell, accept", so a
    user-defined `__eq__` cannot throw out of `encode_lane` past its
    documented contract.
    """
    if not isinstance(value, numbers.Number):
        return False
    try:
        # `!=` through operator, not the literal, so mypy does not reject
        # the intentional cross-type comparison the ABCs make valid.
        return bool(operator.ne(as_int, value))
    except Exception:
        return False


def _as_float(value: LaneInput) -> float:
    """`float(value)`, with a non-numeric `__float__` reported as a TypeError.

    `ArithmeticError` passes through: `float(10**400)` overflows, and that
    is an honest `OverflowError` about the value rather than a fault in
    some `__float__` the type does not even have.
    """
    try:
        return float(value)
    except (TypeError, ValueError, ArithmeticError):
        raise
    except Exception as exc:  # a __float__ that raises something else
        raise TypeError(
            f"cannot encode {type(value).__name__} {value!r} into a lane: "
            f"__float__ raised {exc!r}"
        ) from exc


def decode_lane(lane: int, column_type: ColumnType) -> LaneValue:
    """Unpack one 64-bit lane back into a Python value.

    FLOAT becomes `float`, BOOL becomes `bool`, UINT32 / UINT64 stay
    unsigned, and everything else is read as a signed 64-bit integer.
    """
    if column_type == ColumnType.FLOAT:
        value: float = _FLOAT.unpack(_BITS.pack(lane))[0]
        return value
    if column_type == ColumnType.BOOL:
        return bool(lane)
    if column_type in (ColumnType.UINT32, ColumnType.UINT64):
        return int(lane)
    return int(ctypes.c_int64(lane).value)


def decode_typed_row(row: Any) -> tuple[LaneValue, ...]:
    """Decode a borrowed `TypedRowStruct` into a tuple of Python values.

    The descriptor and its lane storage belong to wirelog only for the
    duration of the callback that received them, so this copies every
    value out before returning.
    """
    values: list[LaneValue] = []
    for c in range(row.logical_ncols):
        lane = int(row.lanes[row.lane_offsets[c]])
        values.append(decode_lane(lane, ColumnType(row.types[c])))
    return tuple(values)


__all__ = ["LaneValue", "LaneInput", "encode_lane", "decode_lane", "decode_typed_row"]
