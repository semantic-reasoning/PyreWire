"""Tests for `Program.relation_ir` (#49 / wirelog#860).

`wirelog_program_get_relation_ir` is a post-wirelog#860 accessor.
On older libwirelog builds (<= 0.41.0) the symbol is absent, so the
suite skips itself when version-detection reports a pre-fix runtime —
the same pattern used by `test_easy_step_snapshot.py`.
"""

from __future__ import annotations

import pytest

try:
    import pyrewire as _pyrewire

    _wirelog_ver = tuple(int(p) for p in _pyrewire.wirelog_version().split("."))
except Exception:
    _wirelog_ver = (0, 0, 0)

pytestmark = pytest.mark.skipif(
    _wirelog_ver <= (0, 41, 0),
    reason=(
        f"Program.relation_ir needs wirelog > 0.41.0 (has wirelog#860); "
        f"running libwirelog reports {'.'.join(str(p) for p in _wirelog_ver)}."
    ),
)


from pyrewire import IRNode, IRNodeType, Program  # noqa: E402

_SINGLE_RULE = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32)
reach(X) :- edge(X, _).
"""

_MULTI_RULE = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32)
reach(X) :- edge(X, _).
reach(X) :- edge(_, X).
"""

_EDB_ONLY = """
.decl edge(x: int32, y: int32)
"""


def test_relation_ir_single_rule_returns_irnode():
    with Program.from_string(_SINGLE_RULE) as p:
        node = p.relation_ir("reach")
        assert node is not None
        assert isinstance(node, IRNode)
        # Walking must yield at least the root itself.
        types = list(node.walk())
        assert len(types) >= 1


def test_relation_ir_multi_rule_returns_union_root():
    with Program.from_string(_MULTI_RULE) as p:
        node = p.relation_ir("reach")
        assert node is not None
        assert node.type == IRNodeType.UNION


def test_relation_ir_unknown_relation_returns_none():
    with Program.from_string(_SINGLE_RULE) as p:
        assert p.relation_ir("does_not_exist") is None


def test_relation_ir_edb_only_returns_none():
    with Program.from_string(_EDB_ONLY) as p:
        assert p.relation_ir("edge") is None


def test_relation_ir_to_str_round_trip():
    with Program.from_string(_SINGLE_RULE) as p:
        node = p.relation_ir("reach")
        assert node is not None
        s = node.to_str()
        assert isinstance(s, str)
        assert s  # non-empty
