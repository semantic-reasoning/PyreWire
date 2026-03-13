"""Tests for Program class."""

import pytest
from pyrewire import Program


class TestProgram:
    """Test cases for Program."""

    def test_declare_relation(self):
        """Test declaring a relation."""
        program = Program()
        program.declare_relation("edge", [("x", "int32"), ("y", "int32")])

        assert "edge" in program.relations
        assert program.relations["edge"] == [("x", "int32"), ("y", "int32")]

    def test_add_fact(self):
        """Test adding a fact."""
        program = Program()
        program.declare_relation("edge", [("x", "int32"), ("y", "int32")])
        program.add_fact("edge", [1, 2])

        assert len(program.facts) == 1
        assert program.facts[0] == ("edge", [1, 2])

    def test_add_rule(self):
        """Test adding a rule."""
        program = Program()
        rule = "reach(Y) :- reach(X), edge(X, Y)."
        program.add_rule(rule)

        assert len(program.rules) == 1
        assert program.rules[0] == rule

    def test_evaluate(self):
        """Test evaluating a program."""
        program = Program()
        result = program.evaluate()

        assert result is not None
        assert result.get_relation("nonexistent") == []
