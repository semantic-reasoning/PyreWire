"""Main Program interface for Wirelog."""

from typing import Any, List, Tuple


class Program:
    """A Wirelog program wrapper."""

    def __init__(self):
        """Initialize a new Wirelog program."""
        self.relations = {}
        self.facts = []
        self.rules = []

    def declare_relation(self, name: str, fields: List[Tuple[str, str]]) -> None:
        """
        Declare a relation.

        Args:
            name: Relation name
            fields: List of (field_name, field_type) tuples
        """
        self.relations[name] = fields

    def add_fact(self, relation: str, values: List[Any]) -> None:
        """
        Add a fact to the program.

        Args:
            relation: Relation name
            values: Values for the fact
        """
        self.facts.append((relation, values))

    def add_rule(self, rule: str) -> None:
        """
        Add a rule to the program.

        Args:
            rule: Rule in Datalog syntax
        """
        self.rules.append(rule)

    def evaluate(self) -> "Result":
        """
        Evaluate the program.

        Returns:
            Result object containing query results
        """
        # TODO: Implement evaluation via Wirelog C FFI
        from pyrewire.result import Result

        return Result()
