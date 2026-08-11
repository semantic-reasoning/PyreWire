# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Run every ported example and assert the result is well-formed (#35).

We don't pin specific row contents because some examples include
floats / aggregates whose representations may shift with wirelog
upgrades. Instead each entry declares a minimum cardinality and
required key — enough to catch a silent regression to "0 rows", but
loose enough to survive cosmetic upstream changes.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _examples_available() -> bool:
    return _EXAMPLES_DIR.is_dir() and any(_EXAMPLES_DIR.glob("*.py"))


pytestmark = pytest.mark.skipif(
    not _examples_available(),
    reason="examples/ directory not populated",
)


def _import_example(name: str) -> Any:
    if str(_EXAMPLES_DIR.parent) not in sys.path:
        sys.path.insert(0, str(_EXAMPLES_DIR.parent))
    return importlib.import_module(f"examples.{name}")


@pytest.mark.parametrize(
    "module_name,expected_relation,min_rows",
    [
        ("01_simple", "ancestor", 1),
        ("02_reachability", "reach", 1),
        ("03_bitwise", "result", 1),
        ("04_hash_functions", "unique_record", 4),
        ("05_crc32_checksum", "frame_crc", 6),
        ("06_timestamp_lww", "latest", 1),
        ("07_multi_source_analysis", "integrated", 10),
        ("12_batch_vs_session", "batch_reach", 1),
        ("csv_adapter_reachability", "reach", 6),
    ],
)
def test_example_returns_nonempty_relation(
    module_name: str, expected_relation: str, min_rows: int
) -> None:
    mod = _import_example(module_name)
    assert hasattr(mod, "run"), f"{module_name} missing run() entry point"
    out = mod.run()
    assert isinstance(out, dict), f"{module_name}.run() must return a dict"
    assert (
        expected_relation in out
    ), f"{module_name}.run() did not return relation {expected_relation!r}"
    rows = out[expected_relation]
    assert isinstance(rows, list)
    assert len(rows) >= min_rows, (
        f"{module_name}.run()[{expected_relation!r}] returned only "
        f"{len(rows)} rows; expected at least {min_rows}"
    )


def test_hash_functions_example_validates_stored_checksums() -> None:
    mod = _import_example("04_hash_functions")
    out = mod.run()
    assert set(out["valid_record"]) == {
        (1, "alice"),
        (2, "bob"),
        (3, "carol"),
        (4, "alice_dup"),
        (6, "bob_dup"),
    }
    assert set(out["corrupted_record"]) == {(5, "dave", 1234567890123456789, -8213464378072455284)}


def test_crc32_checksum_example_partitions_frames_by_stored_checksum() -> None:
    """`crc32_ethernet()` agrees with the stored CRCs from wirelog 0.54.0 on.

    Through wirelog 0.53.0 the built-in computed a checksum that matched no
    stored value, so every frame landed in `corrupt_frame` and this test
    pinned that as "current main head behavior". The expectations below are
    wirelog's own golden output for `examples/05-crc32-checksum`, which
    became a checked example in 0.54.0.
    """
    if _wirelog_ver() < (0, 54, 0):
        pytest.skip("crc32_ethernet() matches its stored checksums from wirelog 0.54.0 on")

    mod = _import_example("05_crc32_checksum")
    out = mod.run()
    assert set(out["valid_frame"]) == {
        ("F001", "DEADBEEF0102030405060708", 3838819244),
        ("F002", "CAFEBABE0A0B0C0D0E0F1011", 250819451),
        ("F003", "AABBCCDD1213141516171819", 1661565857),
        ("F005", "FFEEDDCCBBAA998877665544", 2259087609),
    }
    assert set(out["corrupt_frame"]) == {
        ("F004", 9999999999, 2056678491),
        ("F006", 1234567890, 1992588221),
    }


def _wirelog_ver() -> tuple[int, ...]:
    try:
        import pyrewire

        return tuple(int(p) for p in pyrewire.wirelog_version().split("."))
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


_STEP_EXAMPLES_SKIPIF = pytest.mark.skipif(
    _wirelog_ver() <= (0, 41, 0),
    reason=(
        "step()/snapshot example ports need wirelog > 0.41.0 (wirelog#852); "
        "older libwirelog returns empty delta lists. Tracked in wirelog#859."
    ),
)


@_STEP_EXAMPLES_SKIPIF
@pytest.mark.parametrize(
    "module_name,expected_key,min_rows",
    [
        ("08_delta_queries", "step_deltas", 5),
        ("10_recursive_under_update", "phase1_insert_chain", 6),
        ("11_time_evolution", "epoch1_errors_emerge", 2),
        ("12_snapshot_vs_delta", "snapshot_rows", 5),
    ],
)
def test_step_example_returns_nonempty_relation(
    module_name: str, expected_key: str, min_rows: int
) -> None:
    mod = _import_example(module_name)
    assert hasattr(mod, "run"), f"{module_name} missing run() entry point"
    out = mod.run()
    assert isinstance(out, dict), f"{module_name}.run() must return a dict"
    assert expected_key in out, f"{module_name}.run() did not return key {expected_key!r}"
    rows = out[expected_key]
    assert isinstance(rows, list)
    assert len(rows) >= min_rows, (
        f"{module_name}.run()[{expected_key!r}] returned only "
        f"{len(rows)} rows; expected at least {min_rows}"
    )
