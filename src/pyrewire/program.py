"""High-level wrapper around a parsed wirelog program.

`Program` owns a `wirelog_program_t*` and exposes typed introspection:
declared relations and their schemas, stratification, rule counts.
Inline-fact extraction (`Program.facts`) lands in a follow-up (#15).

This module replaces the legacy in-memory stub. The stub's
`declare_relation` / `add_fact` / `add_rule` / `evaluate` API is gone;
callers wanting that workflow should use `BatchProgram` (#17).
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ._core.errors import ParseError
from ._ffi import LIB
from ._ffi import _parser as _parser_ffi  # noqa: F401  -- registers argtypes
from ._ffi._enums import ColumnType, CompoundKind
from ._ffi._types import ParseErrorStruct, ProgramHandle


@dataclass(frozen=True)
class Column:
    """One column of a relation's schema."""

    name: str
    type: ColumnType
    compound_kind: CompoundKind
    compound_functor_id: int
    compound_arity: int
    compound_inline_col_offset: int


@dataclass(frozen=True)
class Schema:
    """Schema of a declared relation."""

    relation: str
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Stratum:
    """A stratum in the stratified program."""

    id: int
    rule_names: tuple[str, ...]
    is_recursive: bool


class Program:
    """Owns a parsed wirelog program. Use as a context manager."""

    def __init__(self, handle: ProgramHandle) -> None:
        if not handle.value:
            raise ParseError("null program handle")
        self._handle: ProgramHandle = handle
        self._closed = False

    # --- factory constructors -----------------------------------------------

    @classmethod
    def from_string(cls, source: str) -> Program:
        """Parse `source` as wirelog source text."""
        rc = ctypes.c_int(0)
        h = LIB.wirelog_parse_string(source.encode("utf-8"), ctypes.byref(rc))
        if not h:
            raise ParseError(f"wirelog_parse_string failed (rc={rc.value})")
        return cls(ProgramHandle(h))

    @classmethod
    def from_file(cls, path: str | Path) -> Program:
        """Parse a `.dl` file. On failure raises `ParseError` with
        line / column / source populated from `wirelog_parse_error_t`."""
        info = ParseErrorStruct()
        h = LIB.wirelog_parse_with_error_info(str(path).encode("utf-8"), ctypes.byref(info))
        if not h:
            msg = info.message.decode() if info.message else f"parse failed at {path}"
            raise ParseError(
                msg,
                line=int(info.line) if info.line else None,
                column=int(info.column) if info.column else None,
                source=info.source.decode() if info.source else None,
            )
        return cls(ProgramHandle(h))

    # --- introspection ------------------------------------------------------

    def schema(self, relation: str) -> Schema | None:
        """Return the `Schema` of a declared relation, or `None` if no
        such relation exists in the program."""
        ptr = LIB.wirelog_program_get_schema(self._handle, relation.encode("utf-8"))
        if not ptr:
            return None
        s = ptr.contents
        cols = tuple(
            Column(
                name=s.columns[i].name.decode() if s.columns[i].name else "",
                type=ColumnType(s.columns[i].type),
                compound_kind=CompoundKind(s.columns[i].compound_kind),
                compound_functor_id=int(s.columns[i].compound_functor_id),
                compound_arity=int(s.columns[i].compound_arity),
                compound_inline_col_offset=int(s.columns[i].compound_inline_col_offset),
            )
            for i in range(int(s.column_count))
        )
        return Schema(
            relation=s.relation_name.decode() if s.relation_name else relation,
            columns=cols,
        )

    def stratum_count(self) -> int:
        return int(LIB.wirelog_program_get_stratum_count(self._handle))

    def stratum(self, idx: int) -> Stratum | None:
        ptr = LIB.wirelog_program_get_stratum(self._handle, ctypes.c_uint32(idx))
        if not ptr:
            return None
        st = ptr.contents
        names = tuple(
            (st.rule_names[i].decode() if st.rule_names[i] else "")
            for i in range(int(st.rule_count))
        )
        return Stratum(
            id=int(st.stratum_id),
            rule_names=names,
            is_recursive=bool(st.is_recursive),
        )

    def strata(self) -> Iterator[Stratum]:
        """Iterate every stratum in id order."""
        for i in range(self.stratum_count()):
            s = self.stratum(i)
            if s is not None:
                yield s

    def rule_count(self) -> int:
        return int(LIB.wirelog_program_get_rule_count(self._handle))

    def is_stratified(self) -> bool:
        return bool(LIB.wirelog_program_is_stratified(self._handle))

    # --- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        if self._closed:
            return
        if self._handle.value:
            LIB.wirelog_program_free(self._handle)
        self._handle = ProgramHandle()
        self._closed = True

    def __enter__(self) -> Program:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        rc = "<closed>" if self._closed else str(self.rule_count())
        return f"Program(rule_count={rc})"


__all__ = ["Program", "Schema", "Column", "Stratum", "ColumnType", "CompoundKind"]
