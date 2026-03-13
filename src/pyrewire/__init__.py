"""PyreWire - Python wrapper for Wirelog declarative dataflow analysis."""

__version__ = "0.1.0"
__author__ = "PyreWire Contributors"
__license__ = "Apache-2.0 OR GPL-3.0-or-later"

# Core exports
from pyrewire.program import Program
from pyrewire.result import Result

__all__ = [
    "Program",
    "Result",
]
