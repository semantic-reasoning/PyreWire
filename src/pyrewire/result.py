"""Result handling for Wirelog evaluation."""

from typing import Any, List


class Result:
    """Represents the result of a Wirelog program evaluation."""

    def __init__(self, relations: dict[str, List[tuple]] | None = None):
        """
        Initialize a Result.

        Args:
            relations: Dictionary mapping relation names to result tuples
        """
        self.relations = relations or {}

    def get_relation(self, name: str) -> List[tuple]:
        """
        Get results for a specific relation.

        Args:
            name: Relation name

        Returns:
            List of result tuples
        """
        return self.relations.get(name, [])

    def __repr__(self) -> str:
        """Return string representation."""
        return f"Result({self.relations})"
