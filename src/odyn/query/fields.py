"""Field accessor for building OData filter expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from odyn.query.expressions import Comparison, InList, _validate_field_name

if TYPE_CHECKING:
    from odyn.query.types import ODataValue

__all__ = [
    "F",
    "Field",
]


@dataclass(frozen=True, slots=True)
class Field:
    """Field reference for building filters.

    Use via the `F` factory: `F.FieldName`

    Examples:
        >>> F.Status == "Active"
        Comparison(field='Status', op='eq', value='Active')
        >>> F.Balance > 1000
        Comparison(field='Balance', op='gt', value=1000)
    """

    name: str

    def __post_init__(self) -> None:
        """Validate field name."""
        _validate_field_name(self.name)

    def __eq__(self, other: ODataValue) -> Comparison:  # type: ignore[override]
        """Equal comparison."""
        return Comparison(self.name, "eq", other)

    def __ne__(self, other: ODataValue) -> Comparison:  # type: ignore[override]
        """Not equal comparison."""
        return Comparison(self.name, "ne", other)

    def __gt__(self, other: ODataValue) -> Comparison:
        """Greater than comparison."""
        return Comparison(self.name, "gt", other)

    def __ge__(self, other: ODataValue) -> Comparison:
        """Greater than or equal comparison."""
        return Comparison(self.name, "ge", other)

    def __lt__(self, other: ODataValue) -> Comparison:
        """Less than comparison."""
        return Comparison(self.name, "lt", other)

    def __le__(self, other: ODataValue) -> Comparison:
        """Less than or equal comparison."""
        return Comparison(self.name, "le", other)

    def is_in(self, values: list[ODataValue]) -> InList:
        """Match any of the given values.

        Args:
            values: List of values to match against.

        Returns:
            InList expression.

        Examples:
            >>> F.Type.is_in(["Sale", "Purchase"]).to_odata()
            "(Type eq 'Sale' or Type eq 'Purchase')"
        """
        return InList(self.name, tuple(values))

    def __hash__(self) -> int:
        """Return hash based on field name."""
        return hash(self.name)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"F.{self.name}"


class _FieldFactory:
    """Factory that creates Field instances via attribute access.

    This is the `F` singleton used throughout the API.

    Examples:
        >>> F.Status
        F.Status
        >>> F.Posting_Date
        F.Posting_Date
    """

    __slots__ = ()

    def __getattr__(self, name: str) -> Field:
        """Create a field."""
        return Field(name)

    def __repr__(self) -> str:
        """Return string representation."""
        return "F"


F: Final[_FieldFactory] = _FieldFactory()
"""Field factory singleton. Access fields via `F.FieldName`."""
