#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Extract one released changelog section into a standalone notes file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def extract_section(changelog_text: str, version: str) -> str:
    heading_re = re.compile(rf"^##\s+\[{re.escape(version)}\]\s+-\s+.+$", re.MULTILINE)
    match = heading_re.search(changelog_text)
    if match is None:
        raise ValueError(f"CHANGELOG.md has no section for version {version!r}")

    section_start = match.start()
    search_start = match.end()
    next_heading = re.search(r"^##\s+", changelog_text[search_start:], re.MULTILINE)
    end = len(changelog_text)
    if next_heading is not None:
        end = search_start + next_heading.start()

    return changelog_text[slice(section_start, end)].rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a ## [VERSION] - ... section from CHANGELOG.md."
    )
    parser.add_argument("changelog", type=Path)
    parser.add_argument("version")
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    try:
        notes = extract_section(args.changelog.read_text(encoding="utf-8"), args.version)
    except FileNotFoundError:
        print(f"ERROR: changelog file not found: {args.changelog}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(notes, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
