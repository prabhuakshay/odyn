"""OData query builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self

from odyn.exceptions import QueryValidationError
from odyn.query.expressions import FilterExpression, Raw

__all__ = [
    "ODataQuery",
]


@dataclass
class ODataQuery:
    """Fluent OData query builder.

    Construct queries using method chaining. All methods return `self`
    for fluent composition.

    Examples:
        >>> from odyn.query import ODataQuery, F
        >>> query = (
        ...     ODataQuery()
        ...     .select("No", "Name", "Balance")
        ...     .filter(F.Status == "Active")
        ...     .filter(F.Balance > 1000)
        ...     .order_by("Name asc")
        ...     .top(100)
        ... )
        >>> query.build()
        {'$select': 'No,Name,Balance', '$filter': "Status eq 'Active' and Balance gt 1000", ...}
    """

    _select: list[str] = field(default_factory=list)
    _filters: list[FilterExpression] = field(default_factory=list)
    _expand: list[str] = field(default_factory=list)
    _order_by: list[str] = field(default_factory=list)
    _top: int | None = None
    _skip: int | None = None
    _count: bool = False

    def select(self, *fields: str) -> Self:
        """Select fields to return.

        Args:
            *fields: Field names to include in the response.

        Returns:
            Self for method chaining.

        Raises:
            QueryValidationError: If any field name is empty.

        Examples:
            >>> ODataQuery().select("No", "Name", "Balance").build()
            {'$select': 'No,Name,Balance'}
        """
        for f in fields:
            if not f or not f.strip():
                raise QueryValidationError("Select field cannot be empty")
        self._select.extend(fields)
        return self

    def filter(self, condition: FilterExpression) -> Self:
        """Add a filter condition.

        Multiple filters are AND'd together.

        Args:
            condition: A FilterExpr (Comparison, InList, And, Or, Raw).

        Returns:
            Self for method chaining.

        Raises:
            TypeError: If condition is not a FilterExpr.

        Examples:
            >>> ODataQuery().filter(F.Status == "Active").build()
            {'$filter': "Status eq 'Active'"}
        """
        if not isinstance(condition, FilterExpression):
            raise TypeError(
                f"filter() requires FilterExpr, got {type(condition).__name__}. Use filter_raw() for raw strings."
            )
        self._filters.append(condition)
        return self

    def filter_raw(self, odata_string: str) -> Self:
        """Add a raw OData filter string (escape hatch).

        Args:
            odata_string: Raw OData filter expression.

        Returns:
            Self for method chaining.

        Examples:
            >>> ODataQuery().filter_raw("contains(Name, 'Corp')").build()
            {'$filter': "contains(Name, 'Corp')"}
        """
        self._filters.append(Raw(odata_string))
        return self

    def expand(self, *relations: str) -> Self:
        """Expand related entities.

        Args:
            *relations: Relation names to expand.

        Returns:
            Self for method chaining.

        Raises:
            QueryValidationError: If any relation name is empty.

        Examples:
            >>> ODataQuery().expand("Customer", "SalesLines").build()
            {'$expand': 'Customer,SalesLines'}
        """
        for r in relations:
            if not r or not r.strip():
                raise QueryValidationError("Expand relation cannot be empty")
        self._expand.extend(relations)
        return self

    def order_by(self, *fields: str) -> Self:
        """Order results by fields.

        Args:
            *fields: Field names with optional "asc" or "desc" suffix.

        Returns:
            Self for method chaining.

        Raises:
            QueryValidationError: If any field specification is empty.

        Examples:
            >>> ODataQuery().order_by("Name asc", "Balance desc").build()
            {'$orderby': 'Name asc,Balance desc'}
        """
        for f in fields:
            if not f or not f.strip():
                raise QueryValidationError("Order by field cannot be empty")
        self._order_by.extend(fields)
        return self

    def top(self, count: int) -> Self:
        """Limit number of results.

        Args:
            count: Maximum number of records to return.

        Returns:
            Self for method chaining.

        Raises:
            QueryValidationError: If count is not a non-negative integer.

        Examples:
            >>> ODataQuery().top(100).build()
            {'$top': '100'}
        """
        if not isinstance(count, int) or count < 0:
            raise QueryValidationError(f"top() requires non-negative integer, got {count!r}")
        self._top = count
        return self

    def skip(self, count: int) -> Self:
        """Skip results (for pagination).

        Args:
            count: Number of records to skip.

        Returns:
            Self for method chaining.

        Raises:
            QueryValidationError: If count is not a non-negative integer.

        Examples:
            >>> ODataQuery().skip(50).build()
            {'$skip': '50'}
        """
        if not isinstance(count, int) or count < 0:
            raise QueryValidationError(f"skip() requires non-negative integer, got {count!r}")
        self._skip = count
        return self

    def count(self, include: bool = True) -> Self:
        """Include total count in response.

        Args:
            include: Whether to include the count (default: True).

        Returns:
            Self for method chaining.

        Examples:
            >>> ODataQuery().count().build()
            {'$count': 'true'}
        """
        self._count = include
        return self

    def build(self) -> dict[str, str]:
        """Build query parameters dictionary.

        Returns:
            Dictionary of OData query parameters.

        Examples:
            >>> ODataQuery().filter(F.Status == "Active").top(10).build()
            {'$filter': "Status eq 'Active'", '$top': '10'}
        """
        params: dict[str, str] = {}

        if self._select:
            params["$select"] = ",".join(self._select)

        if self._filters:
            parts = [f.to_odata() for f in self._filters]
            params["$filter"] = " and ".join(parts)

        if self._expand:
            params["$expand"] = ",".join(self._expand)

        if self._order_by:
            params["$orderby"] = ",".join(self._order_by)

        if self._top is not None:
            params["$top"] = str(self._top)

        if self._skip is not None:
            params["$skip"] = str(self._skip)

        if self._count:
            params["$count"] = "true"

        return params
