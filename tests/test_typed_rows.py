# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for the typed session path: `Session.insert_typed` / `remove_typed`
/ `snapshot_typed`.

These wrap `wirelog_session_insert_typed` and friends, which arrived in
wirelog 0.60.0. They are the only way a FLOAT column reaches a session:
the untyped `insert()` carries `int64_t` lanes and truncates via
`int(v)`, and on a relation that declares a FLOAT column the engine
refuses the untyped entry points outright.
"""

from __future__ import annotations

import ctypes
import math
import struct
from dataclasses import replace

import pytest

from pyrewire import Program, Session
from pyrewire._core.errors import ExecError, TypedRowError, WirelogVersionError
from pyrewire._core.lanes import decode_lane, encode_lane
from pyrewire._ffi._advanced import has_typed_row_api
from pyrewire._ffi._enums import ColumnType, CompoundKind, TypedErrorCode
from pyrewire._ffi._loader import _parse_version, _pep440_base
from pyrewire._ffi._types import (
    TYPED_ERROR_STRUCT_SIZE,
    TYPED_ROW_ABI_VERSION,
    TYPED_ROW_STRUCT_SIZE,
    OnTypedTupleFn,
    TypedErrorStruct,
    TypedRowStruct,
)
from pyrewire._ffi._util import wirelog_version

FLOAT_SRC = """
.decl sample(a: int64, value: float)
.decl seen(a: int64, value: float)
seen(A, V) :- sample(A, V).
"""

INT_SRC = """
.decl edge(x: int64, y: int64)
.decl reach(x: int64, y: int64)
reach(X, Y) :- edge(X, Y).
"""

# Inline facts, so a QUERY-mode session has something to snapshot without
# an insert first. `Session`'s mode machine commits to INCREMENTAL on the
# first insert, which then rejects `snapshot_typed()`.
FLOAT_INLINE_SRC = FLOAT_SRC + """
sample(1, 2.5).
sample(2, 3.5).
"""


def _wirelog_older_than(minimum: tuple[int, int, int]) -> bool:
    return _parse_version(_pep440_base(wirelog_version())) < minimum


typed_api = pytest.mark.skipif(
    _wirelog_older_than((0, 60, 0)),
    reason="the typed row entry points first ship in wirelog 0.60.0",
)


# ----------------------------------------------------------------------
# ABI shape — these hold on any engine, so they are not version-gated.
# ----------------------------------------------------------------------


def test_typed_row_struct_matches_documented_abi():
    """Field order and offsets mirror `wirelog_typed_row_v1_t`.

    A silently reordered field would not fail to compile here; it would
    hand wirelog a descriptor whose pointers land in the wrong slots.
    """
    assert TypedRowStruct.struct_size.offset == 0
    assert TypedRowStruct.abi_version.offset == 4
    assert TypedRowStruct.logical_ncols.offset == 8
    assert TypedRowStruct.physical_nlanes.offset == 12
    assert TypedRowStruct.physical_stride.offset == 16
    # Four pointers, naturally aligned after the header.
    assert TypedRowStruct.types.offset == 24
    assert TypedRowStruct.lane_offsets.offset == 32
    assert TypedRowStruct.physical_types.offset == 40
    assert TypedRowStruct.lanes.offset == 48
    assert TYPED_ROW_STRUCT_SIZE == ctypes.sizeof(TypedRowStruct)


def test_typed_error_struct_matches_documented_abi():
    assert TypedErrorStruct.struct_size.offset == 0
    assert TypedErrorStruct.code.offset == 4
    assert TypedErrorStruct.row_index.offset == 8
    assert TypedErrorStruct.logical_col.offset == 12
    assert TypedErrorStruct.message.offset == 16
    assert TypedErrorStruct.message_capacity.offset == 24
    assert TYPED_ERROR_STRUCT_SIZE == ctypes.sizeof(TypedErrorStruct)


def test_typed_error_message_is_a_writeable_buffer():
    """`message` must be `POINTER(c_char)`, not `c_char_p`.

    `c_char_p` surfaces in Python as an immutable `bytes`, so wirelog's
    bounded diagnostic would be written into a buffer nothing can read
    back.
    """
    assert TypedErrorStruct.message.__get__ is not None
    field_type = dict(TypedErrorStruct._fields_)["message"]
    assert field_type is not ctypes.c_char_p
    assert field_type == ctypes.POINTER(ctypes.c_char)


def test_typed_tuple_callback_signature():
    assert OnTypedTupleFn._restype_ is None
    assert OnTypedTupleFn._argtypes_ == (
        ctypes.c_char_p,
        ctypes.POINTER(TypedRowStruct),
        ctypes.c_int32,
        ctypes.c_void_p,
    )


def test_typed_error_codes_match_the_c_enum():
    assert int(TypedErrorCode.NONE) == 0
    assert int(TypedErrorCode.DESCRIPTOR) == 1
    assert int(TypedErrorCode.SCHEMA) == 2
    assert int(TypedErrorCode.VALUE) == 3


def test_abi_version_is_one():
    assert TYPED_ROW_ABI_VERSION == 1


# ----------------------------------------------------------------------
# Lane encoding — pure, so no engine needed.
# ----------------------------------------------------------------------


def test_float_lane_roundtrips_through_ieee754_bits():
    for value in (2.5, -0.0, 0.0, 1e308, -1e-308, math.pi):
        lane = encode_lane(value, ColumnType.FLOAT)
        assert lane == struct.unpack("<Q", struct.pack("<d", value))[0]
        decoded = decode_lane(lane, ColumnType.FLOAT)
        assert decoded == value or (math.isnan(decoded) and math.isnan(value))


def test_float_lane_preserves_sign_of_zero_across_the_encoding():
    """The encoder itself must not flatten `-0.0`; only the engine does.

    Conflating the two would hide where the canonicalization happens and
    make `remove_typed(-0.0)` look like a PyreWire bug rather than the
    documented ingress rule.
    """
    negative = encode_lane(-0.0, ColumnType.FLOAT)
    positive = encode_lane(0.0, ColumnType.FLOAT)
    assert negative != positive
    assert math.copysign(1.0, decode_lane(negative, ColumnType.FLOAT)) < 0


def test_negative_int_lane_roundtrips_as_twos_complement():
    lane = encode_lane(-17, ColumnType.INT64)
    assert lane == (-17) & 0xFFFFFFFFFFFFFFFF
    assert decode_lane(lane, ColumnType.INT64) == -17


def test_unsigned_columns_decode_unsigned():
    lane = encode_lane(2**63 + 5, ColumnType.UINT64)
    assert decode_lane(lane, ColumnType.UINT64) == 2**63 + 5
    # The same bits read as INT64 are negative — the type is what decides.
    assert decode_lane(lane, ColumnType.INT64) < 0


def test_bool_column_decodes_bool():
    assert decode_lane(1, ColumnType.BOOL) is True
    assert decode_lane(0, ColumnType.BOOL) is False


def test_non_integral_float_into_an_int_column_is_rejected():
    with pytest.raises(ValueError, match="cannot store float"):
        encode_lane(2.5, ColumnType.INT64)
    # An integral float is fine — it names an exact integer.
    assert encode_lane(3.0, ColumnType.INT64) == 3


# ----------------------------------------------------------------------
# Engine round-trips.
#
# `Session`'s mode machine commits to INCREMENTAL on the first insert and
# to QUERY on the first snapshot, so a session does one or the other. The
# incremental tests read results back through `step_typed()`; the query
# tests seed their facts inline in the program.
# ----------------------------------------------------------------------


@typed_api
def test_insert_typed_roundtrips_a_float_column():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [(1, 2.5), (2, 3.5)])
        events = sorted(s.step_typed())
    assert events == [("seen", (1, 2.5), 1), ("seen", (2, 3.5), 1)]
    assert all(isinstance(row[1], float) for _rel, row, _diff in events)


@typed_api
def test_untyped_insert_rejects_a_float_where_typed_insert_accepts_it():
    """The regression this whole path exists to prevent.

    `insert()` carries int64 lanes, so 2.5 cannot survive it. Pinning the
    contrast keeps someone from "simplifying" `insert_typed` back onto the
    untyped entry point.
    """
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        with pytest.raises((ExecError, ValueError, TypeError)):
            s.insert("sample", [(1, 2.5)])


@typed_api
def test_untyped_delta_callback_is_refused_on_a_float_program():
    """Why `step_typed()` exists at all.

    wirelog returns `WIRELOG_ERR_EXEC` from
    `wirelog_session_set_delta_cb` when the schema carries a FLOAT column,
    so the untyped `step()` cannot drive such a session.
    """
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [(1, 2.5)])
        with pytest.raises(ExecError):
            s.step()

    # The same program steps fine through the typed callback.
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [(1, 2.5)])
        assert s.step_typed() == [("seen", (1, 2.5), 1)]


@typed_api
def test_snapshot_typed_reads_float_columns_the_untyped_path_cannot():
    """On a FLOAT program the untyped read path is refused outright.

    wirelog will not install an untyped tuple callback when the schema
    carries a FLOAT column, so `snapshot()` returns `WIRELOG_ERR_EXEC`.
    `snapshot_typed()` is not merely nicer here - it is the only one that
    works.
    """
    with Program.from_string(FLOAT_INLINE_SRC) as prog, Session(prog) as s:
        typed_rows = sorted(values for name, values in s.snapshot_typed() if name == "seen")
    assert typed_rows == [(1, 2.5), (2, 3.5)]

    with Program.from_string(FLOAT_INLINE_SRC) as prog, Session(prog) as s:
        with pytest.raises(ExecError):
            s.snapshot()


@typed_api
def test_snapshot_typed_and_snapshot_agree_on_an_int_only_program():
    """Where both paths are allowed, the typed one adds no distortion."""
    src = INT_SRC + "\nedge(1, 2).\nedge(2, 3).\n"
    with Program.from_string(src) as prog, Session(prog) as s:
        typed_rows = sorted(values for name, values in s.snapshot_typed() if name == "reach")
    with Program.from_string(src) as prog, Session(prog) as s:
        raw_rows = sorted(values for name, values in s.snapshot() if name == "reach")
    assert typed_rows == raw_rows == [(1, 2), (2, 3)]


@typed_api
def test_insert_typed_canonicalizes_signed_zero():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [(1, -0.0)])
        events = s.step_typed()
    [(relation, (key, value), diff)] = events
    assert (relation, key, diff) == ("seen", 1, 1)
    assert value == 0.0
    assert math.copysign(1.0, value) > 0


@typed_api
def test_remove_typed_retracts_a_float_row():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [(1, 2.5), (2, 3.5)])
        assert len(s.step_typed()) == 2
        s.remove_typed("sample", [(1, 2.5)])
        assert s.step_typed() == [("seen", (1, 2.5), -1)]


@typed_api
def test_remove_typed_with_negative_zero_retracts_a_positive_zero_row():
    """Both spellings canonicalize on ingress, so the retraction lands."""
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [(1, 0.0)])
        assert s.step_typed() == [("seen", (1, 0.0), 1)]
        s.remove_typed("sample", [(1, -0.0)])
        assert s.step_typed() == [("seen", (1, 0.0), -1)]


@typed_api
def test_typed_path_works_for_a_plain_int_relation():
    """Nothing about the typed path is float-specific."""
    with Program.from_string(INT_SRC) as prog, Session(prog) as s:
        s.insert_typed("edge", [(1, 2), (2, 3)])
        events = sorted(s.step_typed())
    assert events == [("reach", (1, 2), 1), ("reach", (2, 3), 1)]


@typed_api
def test_empty_rows_is_a_no_op():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", [])
        s.remove_typed("sample", [])
        assert s.step_typed() == []


@typed_api
def test_registered_typed_callback_is_stored_but_never_invoked():
    """`fn` arms the trampoline; the events come back from `step_typed()`.

    The registered callable is deliberately NOT called per row -- the
    untyped `set_delta_callback` behaves the same way, and only
    `EasySession.step` dispatches to a user callable. Pinning it here so
    the docstring and the behavior cannot drift apart again: the previous
    version of this test was named "...delivers_decoded_rows" and asserted
    nothing about `fn`, which is exactly the claim that was false.
    """
    calls: list[tuple] = []

    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.set_typed_delta_callback(lambda rel, row, diff: calls.append((rel, row, diff)))
        s.insert_typed("sample", [(1, 2.5)])
        events = s.step_typed()

    assert events == [("seen", (1, 2.5), 1)]
    assert calls == []


@typed_api
def test_clear_typed_delta_callback():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.set_typed_delta_callback(lambda rel, row, diff: None)
        s.set_typed_delta_callback(None)


# ----------------------------------------------------------------------
# Error surface.
# ----------------------------------------------------------------------


@typed_api
def test_wrong_row_width_names_the_row_before_reaching_the_engine():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        with pytest.raises(ValueError, match=r"row 1 has 1 cols, expected 2"):
            s.insert_typed("sample", [(1, 2.5), (2,)])


@typed_api
def test_undeclared_relation_raises_exec_error():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        with pytest.raises(ExecError, match="no schema for relation"):
            s.insert_typed("nope", [(1, 2.5)])


@typed_api
def test_column_types_come_from_the_program_schema():
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        assert s._column_types("sample") == (ColumnType.INT64, ColumnType.FLOAT)


@typed_api
def test_typed_row_error_carries_the_engine_diagnostic():
    """A row wirelog rejects must arrive with its detail attached.

    The generic path raises a bare `ExecError` reading "execution error";
    the point of threading `wirelog_typed_error_v1_t` through is that the
    caller learns the code, the row, and the engine's own message.
    """
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        # A descriptor whose arity disagrees with the relation. Built by
        # hand because `insert_typed` derives the width from the schema and
        # would reject this before the FFI call ever happens.
        lanes = (ctypes.c_uint64 * 1)(7)
        codes = (ctypes.c_uint32 * 1)(int(ColumnType.INT64))
        offsets = (ctypes.c_uint32 * 1)(0)
        row = TypedRowStruct(
            struct_size=TYPED_ROW_STRUCT_SIZE,
            abi_version=TYPED_ROW_ABI_VERSION,
            reserved=0,
            logical_ncols=1,
            physical_nlanes=1,
            physical_stride=1,
            types=codes,
            lane_offsets=offsets,
            physical_types=codes,
            lanes=lanes,
        )
        s._build_typed_rows = lambda rows, types: (
            (TypedRowStruct * 1)(row),
            1,
            [lanes, codes, offsets],
        )

        with pytest.raises(TypedRowError) as excinfo:
            s.insert_typed("sample", [(1, 2.5)])

    err = excinfo.value
    assert isinstance(err, ExecError)  # existing handlers still catch it
    assert err.typed_code != int(TypedErrorCode.NONE)
    assert "relation 'sample'" in str(err)
    assert err.engine_message  # wirelog filled the caller-owned buffer


@typed_api
def test_non_finite_float_is_rejected_by_the_engine_naming_the_row():
    """The reachable `VALUE` error, through the real descriptor builder.

    The monkeypatched test above forges a descriptor `insert_typed` can
    never produce, so it pins neither `row_index` accuracy nor which code
    is reported. This one goes through `_build_typed_rows` unmodified.
    """
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        rows = [(1, 1.5), (2, 2.5), (3, float("nan")), (4, 4.5)]
        with pytest.raises(TypedRowError) as excinfo:
            s.insert_typed("sample", rows)

        err = excinfo.value
        assert err.typed_code == int(TypedErrorCode.VALUE)
        assert err.row_index == 2  # the NaN row, not the first or the last
        assert err.column == 1
        assert "non-finite" in (err.engine_message or "")

        # The batch is validated as a whole: nothing before the bad row
        # was applied.
        assert s.step_typed() == []


@typed_api
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_every_non_finite_spelling_is_rejected(value):
    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        with pytest.raises(TypedRowError):
            s.insert_typed("sample", [(1, value)])


@typed_api
def test_string_in_a_typed_row_is_rejected_rather_than_coerced():
    """`int("5")` is 5, which is a valid intern id for some other symbol.

    The advanced Session has no forward-intern entry point, so there is
    nothing here that could turn text into the right id. Refuse instead of
    writing a wrong one.
    """
    with Program.from_string(INT_SRC) as prog, Session(prog) as s:
        with pytest.raises(TypeError, match="intern id"):
            s.insert_typed("edge", [("5", 2)])


@typed_api
def test_snapshot_typed_reraises_a_decode_error_instead_of_truncating():
    """A raise inside the callback must not become a short row set.

    Through a raw ctypes callback the exception is swallowed at the C
    boundary and the method returns the rows decoded so far with a
    WIRELOG_OK return code -- a silently wrong answer. Routing through
    `CallbackHandle` stashes it and `drain()` re-raises.
    """
    # The decode happens inside the trampoline, so patch it there.
    import pyrewire._core.callbacks as callbacks_mod

    calls = {"n": 0}

    def exploding_decode(row):
        calls["n"] += 1
        raise RuntimeError("decode boom")

    with Program.from_string(FLOAT_INLINE_SRC) as prog, Session(prog) as s:
        original = callbacks_mod.decode_typed_row
        callbacks_mod.decode_typed_row = exploding_decode
        try:
            with pytest.raises(RuntimeError, match="decode boom"):
                s.snapshot_typed()
        finally:
            callbacks_mod.decode_typed_row = original

    assert calls["n"] > 0  # the callback really ran


@typed_api
def test_typed_and_untyped_callbacks_do_not_share_a_handle():
    """Switching kinds must re-arm, not reuse the other kind's handle.

    Reusing it hands `OnTypedTupleFn` to `wirelog_session_set_delta_cb`,
    which ctypes rejects with an opaque ArgumentError after `user_fn` has
    already been overwritten.
    """
    with Program.from_string(INT_SRC) as prog, Session(prog) as s:
        s.set_typed_delta_callback(lambda *a: None)
        assert s._delta_cb is not None and s._delta_cb.kind == "typed_delta"

        s.set_delta_callback(lambda *a: None)
        assert s._delta_cb is not None and s._delta_cb.kind == "delta"

        s.insert("edge", [(1, 2)])
        assert s.step() == [("reach", (1, 2), 1)]


@typed_api
def test_closing_a_session_clears_through_the_armed_kinds_entry_point():
    """`close()` must call the clear matching the armed kind.

    Asserting only `_delta_cb is None` afterwards pins nothing: the old
    code set that too, so the test stayed green with the kind dispatch
    reverted. Record which C entry point was actually called.
    """
    from pyrewire._ffi import LIB

    for src, kind, expected in (
        (FLOAT_SRC, "typed_delta", "wirelog_session_set_typed_delta_cb"),
        (INT_SRC, "delta", "wirelog_session_set_delta_cb"),
    ):
        called: list[str] = []
        real_typed = LIB.wirelog_session_set_typed_delta_cb
        real_untyped = LIB.wirelog_session_set_delta_cb

        with Program.from_string(src) as prog:
            s = Session(prog)
            if kind == "typed_delta":
                s.set_typed_delta_callback(lambda *a: None)
            else:
                s.set_delta_callback(lambda *a: None)
            assert s._delta_cb is not None and s._delta_cb.kind == kind

            def _typed(*a, _r=real_typed):
                called.append("wirelog_session_set_typed_delta_cb")
                return _r(*a)

            def _untyped(*a, _r=real_untyped):
                called.append("wirelog_session_set_delta_cb")
                return _r(*a)

            LIB.wirelog_session_set_typed_delta_cb = _typed
            LIB.wirelog_session_set_delta_cb = _untyped
            try:
                s.close()
            finally:
                LIB.wirelog_session_set_typed_delta_cb = real_typed
                LIB.wirelog_session_set_delta_cb = real_untyped

        assert called == [expected], f"{kind}: {called}"
        assert s._delta_cb is None


@typed_api
def test_snapshot_typed_releases_its_registry_slot_on_the_raising_path():
    """Pin the `finally: cb.close()`, not refcounting.

    Counting `_REGISTRY` after a successful call proves nothing:
    `CallbackHandle.__del__` reclaims the slot by refcount whether or not
    `close()` ran, so such a test passes with the `finally` deleted. The
    explicit close is load-bearing exactly when the call raises - the
    propagating traceback pins the frame holding `cb`, so `__del__` does
    not fire promptly. Drive that path.
    """
    import pyrewire._core.callbacks as callbacks_mod

    with Program.from_string(FLOAT_INLINE_SRC) as prog, Session(prog) as s:
        before = len(callbacks_mod._REGISTRY)

        original = callbacks_mod.decode_typed_row

        def boom(row):
            raise RuntimeError("decode boom")

        callbacks_mod.decode_typed_row = boom
        try:
            with pytest.raises(RuntimeError, match="decode boom"):
                s.snapshot_typed()
        finally:
            callbacks_mod.decode_typed_row = original

        # Still inside the frame that caught the exception, so the
        # traceback may still reference the failed call. Only the explicit
        # close() can have released the slot by now.
        assert len(callbacks_mod._REGISTRY) == before


@typed_api
def test_step_typed_rearms_after_an_untyped_callback_was_installed():
    """Switching kinds into `step_typed()` must re-arm, not reuse."""
    with Program.from_string(INT_SRC) as prog, Session(prog) as s:
        s.set_delta_callback(lambda *a: None)
        assert s._delta_cb is not None and s._delta_cb.kind == "delta"

        s.insert_typed("edge", [(1, 2)])
        assert s.step_typed() == [("reach", (1, 2), 1)]
        assert s._delta_cb is not None and s._delta_cb.kind == "typed_delta"


@typed_api
def test_row_count_comes_from_what_was_built_not_a_second_len():
    """A `Sequence` whose `__len__` changes must not make C read past the end.

    Sizing the descriptor array from one `len(rows)` and handing C a
    second one lets wirelog walk off the allocation. Both now come from
    the materialized list.
    """

    class ShiftyLen(list):
        def __init__(self, items):
            super().__init__(items)
            self._calls = 0

        def __len__(self):
            self._calls += 1
            return super().__len__() if self._calls <= 2 else 64

    with Program.from_string(FLOAT_SRC) as prog, Session(prog) as s:
        s.insert_typed("sample", ShiftyLen([(1, 1.5)]))
        # Exactly the one real row was inserted; no descriptor beyond it
        # was ever handed to the engine.
        assert s.step_typed() == [("seen", (1, 1.5), 1)]


def test_encode_lane_accepts_index_and_float_protocols():
    """NumPy scalars go through `insert_batch`; they must work here too."""

    class Indexy:
        def __index__(self):
            return 7

    class Floaty:
        def __float__(self):
            return 2.5

    assert encode_lane(Indexy(), ColumnType.INT64) == 7
    assert decode_lane(encode_lane(Floaty(), ColumnType.FLOAT), ColumnType.FLOAT) == 2.5
    # Float-like into an integer column still has to name an exact integer.
    with pytest.raises(ValueError, match="cannot store float"):
        encode_lane(Floaty(), ColumnType.INT64)
    with pytest.raises(TypeError, match="cannot encode"):
        encode_lane(object(), ColumnType.INT64)


def test_integral_float_only_value_is_accepted_not_falsely_rejected():
    """A bare `__float__` provider has nothing to lose.

    The lossiness guard compares the float result against the original,
    which is only meaningful for a real numeric type. A plain
    `__float__` wrapper has no numeric `__eq__`, so that comparison falls
    back to identity and rejects every such value while claiming it was
    unrepresentable. The previous guard did exactly that.

    The existing protocol test uses 2.5, which short-circuits at the
    integrality check and never reaches the comparison - which is why
    nothing caught it.
    """

    class Meters:
        def __init__(self, v):
            self.v = v

        def __float__(self):
            return self.v

    assert encode_lane(Meters(4.0), ColumnType.INT64) == 4
    assert encode_lane(Meters(-7.0), ColumnType.INT64) == (-7) & 0xFFFFFFFFFFFFFFFF
    assert decode_lane(encode_lane(Meters(2.5), ColumnType.FLOAT), ColumnType.FLOAT) == 2.5
    # Non-integral into an integer column is still refused.
    with pytest.raises(ValueError, match="cannot store float"):
        encode_lane(Meters(2.5), ColumnType.INT64)


def test_a_raising_eq_cannot_escape_encode_lane():
    """The guard must not let a user `__eq__` throw past the contract.

    `EqBoom` has to be registered as a `numbers.Number`, or it returns at
    the isinstance gate and never reaches the comparison this test is
    about - which is what the first version of it did.
    """
    import numbers

    class EqBoom:
        def __float__(self):
            return 4.0

        def __eq__(self, other):
            raise KeyError("boom")

    numbers.Number.register(EqBoom)

    assert encode_lane(EqBoom(), ColumnType.INT64) == 4


def test_int_too_large_for_float_keeps_its_overflow_error():
    """`float(10**400)` overflowing is about the value, not a `__float__`.

    Reporting it as a TypeError blaming `__float__` would be doubly
    wrong: `int` has no `__float__`, and the value is integer-like.
    """
    with pytest.raises(OverflowError):
        encode_lane(10**400, ColumnType.FLOAT)


def test_lossy_integer_like_is_refused_rather_than_stored_wrong():
    """`Decimal(2**63-1)` names an integer no binary64 can hold.

    Routing it through `float` would store 2**63, one off from the value
    the caller named, with no error. Refuse instead.
    """
    from decimal import Decimal

    exact = Decimal(2**53)  # representable
    assert encode_lane(exact, ColumnType.INT64) == 2**53

    with pytest.raises(ValueError, match="not exactly representable"):
        encode_lane(Decimal(2**63 - 1), ColumnType.INT64)

    from fractions import Fraction

    assert encode_lane(Fraction(3, 1), ColumnType.INT64) == 3
    with pytest.raises(ValueError, match="not exactly representable"):
        encode_lane(Fraction(2**63 - 1, 1), ColumnType.INT64)


def test_index_returning_a_non_int_is_a_clean_type_error():
    """`operator.index` enforces the protocol's own contract.

    Calling `__index__()` directly would let a bogus return value reach
    the mask and fail as an unrelated operand error.
    """

    class Liar:
        def __index__(self):
            return "not an int"

    with pytest.raises(TypeError, match="__index__ returned non-int"):
        encode_lane(Liar(), ColumnType.INT64)


def test_a_raising_float_conversion_is_reported_as_a_type_error():
    class Exploding:
        def __float__(self):
            raise RuntimeError("boom")

    with pytest.raises(TypeError, match="__float__ raised"):
        encode_lane(Exploding(), ColumnType.FLOAT)


def test_encode_lane_accepts_numpy_scalars_when_numpy_is_present():
    np = pytest.importorskip("numpy")
    assert encode_lane(np.int64(5), ColumnType.INT64) == 5
    assert encode_lane(np.int32(-3), ColumnType.INT64) == (-3) & 0xFFFFFFFFFFFFFFFF
    assert decode_lane(encode_lane(np.float64(2.5), ColumnType.FLOAT), ColumnType.FLOAT) == 2.5


@typed_api
def test_inline_compound_relation_is_refused_with_a_clear_message():
    """`_column_types` builds a flat one-lane-per-column descriptor, which
    an inline compound column does not fit. Refuse loudly rather than hand
    wirelog a descriptor whose lanes mean something else."""
    with Program.from_string(INT_SRC) as prog, Session(prog) as s:
        real = prog.schema("edge")
        assert real is not None
        inline_col = replace(real.columns[1], compound_kind=CompoundKind.INLINE)
        patched = replace(real, columns=(real.columns[0], inline_col))
        s._program.schema = lambda relation: patched  # type: ignore[method-assign]

        with pytest.raises(ExecError, match="inline compound"):
            s.insert_typed("edge", [(1, 2)])


# ----------------------------------------------------------------------
# Older engines.
# ----------------------------------------------------------------------


def test_typed_api_detection_agrees_with_the_engine_version():
    """`has_typed_row_api()` must track the 0.60.0 boundary.

    The loader floor still admits wirelog 0.52.0, so PyreWire has to keep
    importing there - registering these argtypes unguarded would raise
    `AttributeError` at import time and take the whole package down.
    """
    assert has_typed_row_api() is (not _wirelog_older_than((0, 60, 0)))


@pytest.mark.skipif(
    not _wirelog_older_than((0, 60, 0)),
    reason="covers the pre-0.60.0 engine path",
)
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda s: s.insert_typed("edge", [(1, 2)]), id="insert_typed"),
        pytest.param(lambda s: s.remove_typed("edge", [(1, 2)]), id="remove_typed"),
        pytest.param(lambda s: s.insert_typed("edge", []), id="insert_typed-empty"),
        pytest.param(lambda s: s.snapshot_typed(), id="snapshot_typed"),
        pytest.param(lambda s: s.step_typed(), id="step_typed"),
        pytest.param(lambda s: s.set_typed_delta_callback(lambda *a: None), id="set-cb"),
        pytest.param(lambda s: s.set_typed_delta_callback(None), id="clear-cb"),
    ],
)
def test_every_typed_method_raises_version_error_on_an_older_engine(call):
    """All five guards, not just `insert_typed`'s.

    A mutation dropping the guard from any of the other four left the
    suite green when only `insert_typed` was covered; the symbol is simply
    absent on an older engine, so the failure would surface as a raw
    ctypes `AttributeError` instead of this typed error.
    """
    with Program.from_string(INT_SRC) as prog, Session(prog) as s:
        with pytest.raises(WirelogVersionError, match="0.60.0"):
            call(s)


def test_package_imports_without_the_typed_entry_points(monkeypatch):
    """Simulate an older engine: the guard, not ctypes, must decide."""
    from pyrewire._ffi import _advanced

    monkeypatch.setattr(_advanced, "TYPED_ROW_ENTRY_POINTS", ("wirelog_no_such_symbol",))
    assert _advanced.has_typed_row_api() is False
    # Registration is a no-op in that state rather than an AttributeError.
    _advanced._register()
