"""OData filter expression building and composition.

This module provides a type-safe, composable system for building OData filter
expressions. It supports:

- **Comparison**: Simple field comparisons (e.g., `name eq 'John'`)
- **InList**: IN-style queries via OR-chained equalities
- **Raw**: Escape hatch for unsupported OData syntax
- **And/Or**: Logical combinations with `&` and `|` operators

Example:
    >>> from odyn.query.expressions import Comparison, InList, Raw
    >>> # Simple comparison
    >>> Comparison(field="name", operator="eq", value="John").to_odata()
    "name eq 'John'"

    >>> # Combine with & and |
    >>> (Comparison("age", "gt", 18) & Comparison("active", "eq", True)).to_odata()
    "(age gt 18 and active eq true)"

    >>> # IN-style query
    >>> InList(field="status", values=("active", "pending")).to_odata()
    "(status eq 'active' or status eq 'pending')"

All expression classes implement the `FilterExpression` protocol, allowing
custom expressions to integrate seamlessly with the built-in types.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from odyn.exceptions import QueryValidationError
from odyn.query.types import VALID_OPERATORS, ODataValue

__all__ = [
    "Comparison",
    "InList",
    "Raw",
]


def _validate_field_name(field_name: str) -> None:
    """Validate a field name according to OData identifier rules.

    An OData identifier must:
    - Not be empty.
    - Start with a letter or underscore.
    - Contain only alphanumeric characters or underscores.

    Args:
        field_name: The field name to validate.

    Raises:
        QueryValidationError: If the field name is invalid.
    """
    if not field_name:
        raise QueryValidationError("Field name cannot be empty")
    if not (field_name[0].isalpha() or field_name[0] == "_"):
        raise QueryValidationError(f"Invalid field name '{field_name}': must start with a letter or underscore.")

    if not all(c.isalnum() or c == "_" for c in field_name):
        raise QueryValidationError(
            f"Invalid field name '{field_name}': can only contain alphanumeric characters and underscores."
        )


def _validate_operator(operator: str) -> None:
    """Validate an OData comparison operator.

    Supported operators: eq, ne, gt, ge, lt, le

    Args:
        operator: The operator to validate.

    Raises:
        QueryValidationError: If the operator is invalid.
    """
    if not operator:
        raise QueryValidationError(f"Operator cannot be empty. Supported operators: {', '.join(VALID_OPERATORS)}")
    if operator not in VALID_OPERATORS:
        raise QueryValidationError(
            f"Unsupported operator: {operator}. Supported operators: {', '.join(VALID_OPERATORS)}"
        )


def _validate_value(value: Any) -> None:
    """Validate that a value type is supported for OData queries.

    Args:
        value: The value to validate.

    Raises:
        QueryValidationError: If the value type is not supported.
    """
    if not isinstance(value, bool | int | float | str | date | datetime | None):
        raise QueryValidationError(
            f"Unsupported value type: '{type(value).__name__}'. "
            f"Supported types: bool, int, float, str, date, datetime, None"
        )


def _format_value(value: Any) -> str:
    """Format a value for use in a query string.

    Args:
        value: The value to format.
            Supported types: bool, int, float, str, date, datetime, None

    Returns:
        str: The formatted value suitable for OData filter strings.

    Raises:
        QueryValidationError: If the value type is not supported.
    """
    match value:
        case None:
            return "null"
        case bool():
            return "true" if value else "false"
        case int() | float():
            return str(value)
        case str():
            return f"'{value.replace("'", "''")}'"
        case datetime():
            return value.strftime("%Y-%m-%dT%H:%M:%SZ")
        case date():
            return value.strftime("%Y-%m-%d")
    raise QueryValidationError(
        f"Cannot format value of type '{type(value).__name__}'. "
        f"Supported types: bool, int, float, str, date, datetime, None"
    )


@runtime_checkable
class FilterExpression(Protocol):
    """Protocol for filter expressions.

    All filter expressions must implement the `to_odata() -> str` method.
    This allows third-party libraries to implement their own filter expressions.

    Example:
        >>> class CustomExpression(FilterExpression):
        ...     def to_odata(self) -> str:
        ...         return "custom()"
        >>> isinstance(CustomExpression(), FilterExpression)
        True
    """

    def to_odata(self) -> str:
        """Convert this expression to an OData filter string."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Comparison:
    """A single comparison: <field> <operator> <value>.

    Attributes:
        field: The field name to compare.
        operator: The comparison operator (eq, ne, gt, ge, lt, le).
        value: The value to compare against.

    Example:
        >>> Comparison(field="name", operator="eq", value="John").to_odata()
        'name eq 'John''

        >>> Comparison(field="name", operator="eq", value=True).to_odata()
        'name eq true'
    """

    field: str
    operator: str
    value: ODataValue

    def __post_init__(self) -> None:
        """Validate field, operator and value on initialization."""
        _validate_field_name(self.field)
        _validate_operator(self.operator)
        _validate_value(self.value)

    def to_odata(self) -> str:
        """Convert this expression to an OData filter string.

        Returns:
            str: The OData filter string (e.g., "name eq 'John'")
        """
        return f"{self.field} {self.operator} {_format_value(self.value)}"

    def __and__(self, other: FilterExpression) -> "And":
        """Combine this expression with another using AND.

        Args:
            other: Another filter expression to combine with.

        Returns:
            And: A new And expression containing both expressions.
        """
        return And((self, other))

    def __or__(self, other: FilterExpression) -> "Or":
        """Combine this expression with another using OR.

        Args:
            other: Another filter expression to combine with.

        Returns:
            Or: A new Or expression containing both expressions.
        """
        return Or((self, other))


@dataclass(frozen=True, slots=True)
class InList:
    """An IN expression matching a field against multiple values.

    This generates an OR chain of equality comparisons. OData does not  have
    a native IN operator, so this is the standard workaround.

    Attributes:
        field: The field name to compare.
        values: A tuple of values to match against.

    Example:
        >>> InList(field="name", values=("John", "Doe")).to_odata()
        "(name eq 'John' or name eq 'Doe')"
    """

    field: str
    values: tuple[ODataValue, ...]

    def __post_init__(self) -> None:
        """Validate field and values on initialization."""
        _validate_field_name(self.field)
        if not self.values:
            raise QueryValidationError(
                f"InList for field '{self.field}' requires at least one value. Provide a non-empty tuple of values."
            )
        for value in self.values:
            _validate_value(value)

    def to_odata(self) -> str:
        """Convert this expression to an OData filter string.

        Returns:
            str: The OData filter string (e.g., "(name eq 'John' or name eq 'Doe')")
        """
        parts = [f"{self.field} eq {_format_value(value)}" for value in self.values]
        return f"({' or '.join(parts)})"

    def __and__(self, other: FilterExpression) -> "And":
        """Combine this expression with another using AND.

        Args:
            other: Another filter expression to combine with.

        Returns:
            And: A new And expression containing both expressions.
        """
        return And((self, other))

    def __or__(self, other: FilterExpression) -> "Or":
        """Combine this expression with another using OR.

        Args:
            other: Another filter expression to combine with.

        Returns:
            Or: A new Or expression containing both expressions.
        """
        return Or((self, other))


@dataclass(frozen=True, slots=True)
class Raw:
    """A raw OData filter string (escape hatch for unsupported expressions).

    Use this when you need to write OData syntax not supported by the
    typed expression classes. The expression is passed through without
    validation or modification.

    Attributes:
        expression: The raw OData filter string.

    Example:
        >>> Raw("contains(name, 'John')").to_odata()
        "contains(name, 'John')"

        >>> Raw("startswith(email, 'admin')").to_odata()
        "startswith(email, 'admin')"

    """

    expression: str

    def __post_init__(self) -> None:
        """Validate that the expression is not empty."""
        if not self.expression or not self.expression.strip():
            raise QueryValidationError(
                "Raw expression cannot be empty or whitespace-only. Provide a valid OData filter expression string."
            )

    def to_odata(self) -> str:
        """Convert this expression to an OData filter string.

        Returns:
            str: The OData filter string.
        """
        return self.expression

    def __and__(self, other: FilterExpression) -> "And":
        """Combine this expression with another using AND.

        Args:
            other: Another filter expression to combine with.

        Returns:
            And: A new And expression containing both expressions.
        """
        return And((self, other))

    def __or__(self, other: FilterExpression) -> "Or":
        """Combine this expression with another using OR.

        Args:
            other: Another filter expression to combine with.

        Returns:
            Or: A new Or expression containing both expressions.
        """
        return Or((self, other))


@dataclass(frozen=True, slots=True)
class And:
    """A logical AND combination of filter expressions.

    Combines two or more expressions with OData 'and' operator.
    Typically created using the '&' operator on expressions.

    Attributes:
        expressions: A tuple of filter expressions to combine.

    Example:
    >>> comparison_a = Comparison(field="name", operator="eq", value="John")
    >>> comparison_b = Comparison(field="age", operator="gt", value=18)
    >>> And(comparison_a, comparison_b).to_odata()
    "(name eq 'John' and age gt 18)"
    """

    expressions: tuple[FilterExpression, ...]

    def __post_init__(self) -> None:
        """Validate that expressions is a tuple with at least 2 elements."""
        if not isinstance(self.expressions, tuple):
            raise QueryValidationError(f"And expression requires a tuple of expressions, got {type(self.expressions)}")
        if len(self.expressions) < 2:
            raise QueryValidationError(f"And expression requires at least two expressions, got {len(self.expressions)}")
        for i, expression in enumerate(self.expressions):
            if not isinstance(expression, FilterExpression):
                raise QueryValidationError(
                    f"And expression item at index {i} must implement FilterExpression, got {type(expression)}"
                )

    def to_odata(self) -> str:
        """Convert this expression to an OData filter string.

        Returns:
            str: The OData filter string (e.g., "(name eq 'John' and age gt 18)")
        """
        parts = [expression.to_odata() for expression in self.expressions]
        return f"({' and '.join(parts)})"

    def __and__(self, other: FilterExpression) -> "And":
        """Combine this expression with another using AND.

        Args:
            other: Another filter expression to combine with.

        Returns:
            And: A new And expression containing both expressions.
        """
        return And((*self.expressions, other))

    def __or__(self, other: FilterExpression) -> "Or":
        """Combine this expression with another using OR.

        Args:
            other: Another filter expression to combine with.

        Returns:
            Or: A new Or expression containing both expressions.
        """
        return Or((self, other))


@dataclass(frozen=True, slots=True)
class Or:
    """A logical OR combination of filter expression.

    Combines two or more expressions with OData 'or' operator.
    Typically created using the '|' operator on expressions.

    Attributes:
        expressions: A tuple of filter expressions to combine.

    Example:
    >>> comparison_a = Compare(field="name", operator="eq", value="John")
    >>> comparison_b = Compare(field="age", operator="ne", value=100)
    >>> Or(comparison_a, comparison_b)
    "(name eq 'John' or Age ne 100)"
    """

    expressions: tuple[FilterExpression, ...]

    def __post_init__(self) -> None:
        """Validate that expressions is a tuple with at least 2 elements."""
        if not isinstance(self.expressions, tuple):
            raise QueryValidationError(
                f"Or expression requires a tuple of expressions, got {type(self.expressions).__name__}"
            )
        if len(self.expressions) < 2:
            raise QueryValidationError(f"Or expression requires at least two expressions, got {len(self.expressions)}")
        for i, expression in enumerate(self.expressions):
            if not isinstance(expression, FilterExpression):
                raise QueryValidationError(
                    f"Or expression item at index {i} must implement FilterExpression, got {type(expression).__name__}"
                )

    def to_odata(self) -> str:
        """Convert this expression to an OData filter string.

        Returns:
            str: The OData filter string.
        """
        parts = [expression.to_odata() for expression in self.expressions]
        return f"({' or '.join(parts)})"

    def __and__(self, other: FilterExpression) -> "And":
        """Combine this expression with another using AND.

        Args:
            other: Another filter expression to combine with.

        Returns:
            And: A new And expression containing both expressions.
        """
        return And((self, other))

    def __or__(self, other: FilterExpression) -> "Or":
        """Combine this expression with another using OR.

        Args:
            other: Another filter expression to combine with.

        Returns:
            Or: A new Or expression containing both expressions.
        """
        return Or((*self.expressions, other))
