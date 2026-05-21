"""High-level batch pipeline: Program → optimize → evaluate → Result (#17 / #18).

`BatchProgram` is the simplest way to compute the full IDB closure of a
wirelog program from Python. It owns a `Program`, an executor, and the
optimizer step, and produces a `Result` from `evaluate()`.

Lifetime ordering is enforced by the wrapping classes: the executor is
freed before the program, the result before the executor.

Result rows are extracted by writing the relation to a temporary CSV via
`wirelog_result_write_csv` and re-parsing it with the stdlib `csv`
module. The public wirelog ABI does not yet expose a row iterator on the
result handle, so this is the portable path; the implementation can be
swapped behind the same `Result.relation(name)` API when wirelog adds
one.
"""

from __future__ import annotations

import contextlib
import csv
import ctypes
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import Any

from ._core.errors import ExecError, check
from ._core.stdcapture import capture_c_stdout
from ._ffi import LIB
from ._ffi import _executor as _executor_ffi  # noqa: F401  -- registers argtypes
from ._ffi._enums import ColumnType
from ._ffi._types import ExecutorHandle, ResultHandle
from .program import Program, Schema


def _raise_exec(rc_value: int) -> None:
    """Raise on a failing wirelog call whose out-`rc` may not be set."""
    if rc_value:
        check(rc_value)
    raise ExecError("wirelog call failed (no error code reported)")


class BatchProgram(contextlib.AbstractContextManager["BatchProgram"]):
    """Owns a `Program` plus its executor and exposes the batch
    optimize → evaluate pipeline."""

    def __init__(self, program: Program) -> None:
        self._program = program
        self._executor: ExecutorHandle = ExecutorHandle()
        self._closed = False

    @classmethod
    def from_string(cls, source: str) -> BatchProgram:
        return cls(Program.from_string(source))

    @classmethod
    def from_file(cls, path: str | Path) -> BatchProgram:
        # wirelog's `wirelog_parse_with_error_info` for paths is not yet
        # implemented; read the file ourselves so `BatchProgram.from_file`
        # works against the current library and transparently picks up
        # the C path once wirelog exposes it.
        text = Path(path).read_text(encoding="utf-8")
        return cls(Program.from_string(text))

    # --- pipeline -----------------------------------------------------------

    def optimize(self) -> None:
        """Run wirelog's optimizer over the owned program."""
        self._check_open()
        rc = ctypes.c_int(0)
        ok = LIB.wirelog_optimize(self._program._handle, ctypes.byref(rc))
        if not ok:
            _raise_exec(rc.value)

    def _ensure_executor(self) -> None:
        if self._executor.value:
            return
        rc = ctypes.c_int(0)
        h = LIB.wirelog_executor_create(self._program._handle, ctypes.byref(rc))
        if not h:
            _raise_exec(rc.value)
        self._executor = ExecutorHandle(h)

    def load_facts_from_csv(self, relation: str, csv_path: str | Path) -> None:
        """Load EDB rows for `relation` from a CSV file (batch-only)."""
        self._check_open()
        self._ensure_executor()
        rc = ctypes.c_int(0)
        ok = LIB.wirelog_load_facts_from_csv(
            self._executor,
            relation.encode("utf-8"),
            str(csv_path).encode("utf-8"),
            ctypes.byref(rc),
        )
        if not ok:
            _raise_exec(rc.value)

    def evaluate(self) -> Result:
        """Run the executor and return a `Result` handle."""
        self._check_open()
        self._ensure_executor()
        rc = ctypes.c_int(0)
        h = LIB.wirelog_evaluate(self._executor, ctypes.byref(rc))
        if not h:
            _raise_exec(rc.value)
        return Result(ResultHandle(h), program=self._program)

    def load_all_facts(self) -> None:
        """Load every inline `.dl` fact into the executor.

        Maps to `wirelog_load_all_facts`. Call before `evaluate()` to
        seed the EDB from the program's inline facts.
        """
        self._check_open()
        self._ensure_executor()
        rc = LIB.wirelog_load_all_facts(
            self._program._handle,
            ctypes.cast(self._executor, ctypes.c_void_p),
        )
        if rc != 0:
            check(rc)

    def load_input_files(self) -> None:
        """Process every `.input` directive in the program.

        Maps to `wirelog_load_input_files`. Resolves CSV paths relative
        to the working directory.
        """
        self._check_open()
        self._ensure_executor()
        rc = LIB.wirelog_load_input_files(
            self._program._handle,
            ctypes.cast(self._executor, ctypes.c_void_p),
        )
        if rc != 0:
            check(rc)

    def optimizer_debug(self) -> str:
        """Return the `wirelog_optimizer_debug` output as a string.

        Captures the C-level stdout the function writes through a
        temporary fd-1 redirect.
        """
        self._check_open()
        with capture_c_stdout() as buf:
            LIB.wirelog_optimizer_debug(self._program._handle)
        return buf.getvalue().decode("utf-8", errors="replace")

    # --- lifecycle ----------------------------------------------------------

    @property
    def program(self) -> Program:
        return self._program

    def _check_open(self) -> None:
        if self._closed:
            raise ExecError("BatchProgram is closed")

    def close(self) -> None:
        if self._closed:
            return
        if self._executor.value:
            LIB.wirelog_executor_free(self._executor)
            self._executor = ExecutorHandle()
        if self._program is not None:
            self._program.close()
        self._closed = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


class Result(contextlib.AbstractContextManager["Result"]):
    """Lazy view over a `wirelog_result_t`. Owns the handle; the parent
    `Program` is kept alive for schema lookups."""

    def __init__(self, handle: ResultHandle, *, program: Program) -> None:
        if not handle.value:
            raise ExecError("null result handle")
        self._handle: ResultHandle = handle
        self._program = program
        self._closed = False

    def cardinality(self, relation: str) -> int:
        self._check_open()
        return int(LIB.wirelog_result_relation_cardinality(self._handle, relation.encode("utf-8")))

    def write_csv(self, relation: str, path: str | Path) -> None:
        self._check_open()
        rc = ctypes.c_int(0)
        ok = LIB.wirelog_result_write_csv(
            self._handle,
            relation.encode("utf-8"),
            str(path).encode("utf-8"),
            ctypes.byref(rc),
        )
        if not ok:
            _raise_exec(rc.value)

    def relation(self, name: str) -> list[tuple[Any, ...]]:
        """Materialise all tuples of `name` as Python tuples.

        Columns are converted using the program's declared schema:
        integer / unsigned-integer columns become `int`, `FLOAT` becomes
        `float`, `BOOL` becomes `bool`, and `STRING` is returned as the
        raw symbol text wirelog wrote to the CSV (no intern reverse).
        """
        self._check_open()
        schema = self._program.schema(name)
        fd, tmp_path = tempfile.mkstemp(suffix=".csv", prefix="pyrewire_res_")
        os.close(fd)
        try:
            self.write_csv(name, tmp_path)
            return list(self._read_csv(tmp_path, schema))
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)

    def relation_iter(self, name: str) -> Iterator[tuple[Any, ...]]:
        yield from self.relation(name)

    def _read_csv(self, path: str, schema: Schema | None) -> Iterator[tuple[Any, ...]]:
        with open(path, newline="", encoding="utf-8") as fh:
            for raw in csv.reader(fh):
                if not raw:
                    continue
                if schema is None:
                    yield tuple(raw)
                    continue
                converted: list[Any] = []
                for col, cell in zip(schema.columns, raw, strict=False):
                    if col.type in (
                        ColumnType.INT32,
                        ColumnType.INT64,
                        ColumnType.UINT32,
                        ColumnType.UINT64,
                    ):
                        converted.append(int(cell))
                    elif col.type == ColumnType.FLOAT:
                        converted.append(float(cell))
                    elif col.type == ColumnType.BOOL:
                        converted.append(cell.strip().lower() in ("1", "true", "t"))
                    else:
                        converted.append(cell)
                yield tuple(converted)

    # --- lifecycle ----------------------------------------------------------

    def _check_open(self) -> None:
        if self._closed:
            raise ExecError("Result is closed")

    def close(self) -> None:
        if self._closed:
            return
        if self._handle.value:
            LIB.wirelog_result_free(self._handle)
        self._handle = ResultHandle()
        self._closed = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


__all__ = ["BatchProgram", "Result"]
