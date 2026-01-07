"""Tests for OData filter expression building and validation.

This module provides comprehensive tests for the odyn.query.expressions module,
covering all expression types (Comparison, InList, Raw, And, Or), validation
functions, and value formatting utilities.

Test Categories:
    - Validation functions: _validate_field_name, _validate_operator, _validate_value
    - Value formatting: _format_value for all supported types
    - Protocol compliance: FilterExpression protocol checks
    - Expression classes: Comparison, InList, Raw, And, Or
    - Boolean operators: __and__, __or__ for expression chaining
"""

from datetime import date, datetime

import pytest

from odyn.exceptions import QueryValidationError
from odyn.query.expressions import (
    And,
    Comparison,
    FilterExpression,
    InList,
    Or,
    Raw,
    _format_value,
    _validate_field_name,
    _validate_operator,
    _validate_value,
)
from odyn.query.types import VALID_OPERATORS

# =============================================================================
# Field Name Validation Tests
# =============================================================================


class TestFieldNameValidation:
    """Test suite for OData field name validation.

    OData field names (identifiers) must follow specific rules:
        - Cannot be empty
        - Must start with a letter or underscore
        - Can only contain alphanumeric characters and underscores
    """

    @pytest.mark.parametrize(
        ("field_name", "description"),
        [
            ("valid_field_name", "snake_case identifier"),
            ("valid_field_name_with_123", "snake_case with trailing numbers"),
            ("_valid123", "underscore prefix with numbers"),
            ("valid123", "letter prefix with trailing numbers"),
            ("Name", "single capitalized word"),
            ("firstName", "camelCase identifier"),
            ("UPPERCASE", "all uppercase identifier"),
            ("x", "single character field"),
            ("_", "single underscore"),
        ],
        ids=lambda x: x if isinstance(x, str) and len(x) < 30 else None,
    )
    def test_accepts_valid_odata_identifiers(self, field_name: str, description: str) -> None:
        """Validate that conformant OData identifiers are accepted.

        Args:
            field_name: The field name to validate.
            description: Human-readable description of the test case.
        """
        # Should not raise any exception
        _validate_field_name(field_name)

    @pytest.mark.parametrize(
        "field_name",
        ["", None],
        ids=["empty_string", "none_value"],
    )
    def test_rejects_empty_or_none_field_names(self, field_name: str | None) -> None:
        """Validate that empty or None field names raise QueryValidationError.

        Args:
            field_name: Empty string or None to validate.
        """
        with pytest.raises(QueryValidationError, match="Field name cannot be empty"):
            _validate_field_name(field_name)

    @pytest.mark.parametrize(
        ("field_name", "description"),
        [
            ("123field", "starts with number"),
            ("-invalid_field_name", "starts with hyphen"),
            ("1invalid", "starts with digit"),
            ("~invalid", "starts with tilde"),
            ("@field", "starts with at symbol"),
        ],
        ids=lambda x: x if isinstance(x, str) and not x.startswith(("123", "-", "1", "~", "@")) else None,
    )
    def test_rejects_field_names_with_invalid_first_character(self, field_name: str, description: str) -> None:
        """Validate that field names starting with invalid characters are rejected.

        OData identifiers must start with a letter (a-z, A-Z) or underscore (_).

        Args:
            field_name: The invalid field name to validate.
            description: Human-readable description of the test case.
        """
        with pytest.raises(
            QueryValidationError,
            match=f"Invalid field name '{field_name}': must start with a letter or underscore.",
        ):
            _validate_field_name(field_name)

    def test_rejects_field_name_starting_with_dollar_sign(self) -> None:
        """Validate that field names starting with $ are rejected."""
        with pytest.raises(
            QueryValidationError,
            match=r"Invalid field name '\$field': must start with a letter or underscore\.",
        ):
            _validate_field_name("$field")

    @pytest.mark.parametrize(
        ("field_name", "description"),
        [
            ("invalid-field-name", "contains hyphen"),
            ("invalid.field", "contains period"),
            ("inv@lid", "contains at symbol"),
            ("invalid identifier", "contains space"),
            ("field#name", "contains hash"),
            ("field!name", "contains exclamation mark"),
        ],
        ids=lambda x: x if isinstance(x, str) and any(c in x for c in "-. @#!") else None,
    )
    def test_rejects_field_names_with_invalid_characters(self, field_name: str, description: str) -> None:
        """Validate that field names containing invalid characters are rejected.

        OData identifiers can only contain alphanumeric characters and underscores
        after the first character.

        Args:
            field_name: The invalid field name to validate.
            description: Human-readable description of the test case.
        """
        with pytest.raises(
            QueryValidationError,
            match=(f"Invalid field name '{field_name}': can only contain alphanumeric characters and underscores."),
        ):
            _validate_field_name(field_name)

    def test_rejects_field_name_with_dollar_sign_in_middle(self) -> None:
        """Validate that field names containing $ are rejected."""
        with pytest.raises(
            QueryValidationError,
            match=r"Invalid field name 'field\$name': can only contain alphanumeric characters and underscores\.",
        ):
            _validate_field_name("field$name")


# =============================================================================
# Operator Validation Tests
# =============================================================================


class TestOperatorValidation:
    """Test suite for OData comparison operator validation.

    Supported operators are: eq, ne, gt, ge, lt, le
    These correspond to standard comparison operations in OData.
    """

    @pytest.mark.parametrize(
        ("operator", "meaning"),
        [
            ("eq", "equal to"),
            ("ne", "not equal to"),
            ("gt", "greater than"),
            ("ge", "greater than or equal to"),
            ("lt", "less than"),
            ("le", "less than or equal to"),
        ],
        ids=["eq", "ne", "gt", "ge", "lt", "le"],
    )
    def test_accepts_all_valid_odata_operators(self, operator: str, meaning: str) -> None:
        """Validate that all supported OData operators are accepted.

        Args:
            operator: The operator string to validate.
            meaning: Human-readable description of the operator.
        """
        _validate_operator(operator)

    @pytest.mark.parametrize(
        "operator",
        ["", None],
        ids=["empty_string", "none_value"],
    )
    def test_rejects_empty_or_none_operators(self, operator: str | None) -> None:
        """Validate that empty or None operators raise QueryValidationError.

        Args:
            operator: Empty string or None to validate.
        """
        with pytest.raises(
            QueryValidationError,
            match=f"Operator cannot be empty. Supported operators: {', '.join(VALID_OPERATORS)}",
        ):
            _validate_operator(operator)

    @pytest.mark.parametrize(
        ("operator", "description"),
        [
            ("invalid", "arbitrary invalid string"),
            ("equals", "verbose form of eq"),
            ("EQ", "uppercase version of eq"),
            ("==", "programming equality operator"),
            ("!=", "programming inequality operator"),
            (">", "programming greater-than operator"),
            (">=", "programming greater-or-equal operator"),
            ("<", "programming less-than operator"),
            ("<=", "programming less-or-equal operator"),
            ("contains", "OData function, not operator"),
            ("in", "SQL-style operator"),
        ],
        ids=lambda x: x if isinstance(x, str) and len(x) < 20 else None,
    )
    def test_rejects_unsupported_operators(self, operator: str, description: str) -> None:
        """Validate that unsupported operators raise QueryValidationError.

        Args:
            operator: The unsupported operator to validate.
            description: Human-readable description of the test case.
        """
        with pytest.raises(
            QueryValidationError,
            match=(f"Unsupported operator: {operator}. Supported operators: {', '.join(VALID_OPERATORS)}"),
        ):
            _validate_operator(operator)


# =============================================================================
# Value Validation Tests
# =============================================================================


class TestValueValidation:
    """Test suite for OData value type validation.

    Supported value types: bool, int, float, str, date, datetime, None
    """

    @pytest.mark.parametrize(
        ("value", "description"),
        [
            (True, "boolean true"),
            (False, "boolean false"),
            (-1, "negative integer"),
            (0, "zero integer"),
            (1, "positive integer"),
            (2**31, "large integer"),
            (-1.0, "negative float"),
            (0.0, "zero float"),
            (1.0, "positive float"),
            (3.14159, "decimal float"),
            (-1e10, "scientific notation float"),
            ("string", "regular string"),
            ("", "empty string"),
            ("string with spaces", "string with whitespace"),
            (date.today(), "today's date"),
            (date(2024, 1, 1), "specific date"),
            (datetime.now(), "current datetime"),
            (datetime(2024, 1, 1, 12, 30, 45), "specific datetime"),
            (None, "null value"),
        ],
        ids=lambda x: x if isinstance(x, str) and len(x) < 30 else None,
    )
    def test_accepts_all_supported_value_types(self, value, description: str) -> None:
        """Validate that all supported OData value types are accepted.

        Args:
            value: The value to validate.
            description: Human-readable description of the test case.
        """
        _validate_value(value)

    @pytest.mark.parametrize(
        ("value", "description"),
        [
            ([], "empty list"),
            ([1, 2, 3], "populated list"),
            ({}, "empty dict"),
            ({"key": "value"}, "populated dict"),
            ((), "empty tuple"),
            ((1, 2, 3), "populated tuple"),
            (set(), "empty set"),
            ({1, 2, 3}, "populated set"),
            (object(), "generic object"),
            (lambda x: x, "lambda function"),
        ],
        ids=lambda x: x if isinstance(x, str) else None,
    )
    def test_rejects_unsupported_value_types(self, value, description: str) -> None:
        """Validate that unsupported value types raise QueryValidationError.

        Args:
            value: The unsupported value to validate.
            description: Human-readable description of the test case.
        """
        with pytest.raises(
            QueryValidationError,
            match=(
                f"Unsupported value type: '{type(value).__name__}'. "
                f"Supported types: bool, int, float, str, date, datetime, None"
            ),
        ):
            _validate_value(value)


# =============================================================================
# Value Formatting Tests
# =============================================================================


class TestValueFormatting:
    """Test suite for OData value formatting.

    Tests the _format_value function which converts Python values
    to their OData string representations.
    """

    @pytest.mark.parametrize(
        ("value", "expected", "description"),
        [
            (None, "null", "None formats to 'null'"),
            (True, "true", "True formats to lowercase 'true'"),
            (False, "false", "False formats to lowercase 'false'"),
        ],
        ids=["none", "true", "false"],
    )
    def test_formats_null_and_boolean_values(self, value, expected: str, description: str) -> None:
        """Validate null and boolean value formatting.

        Args:
            value: The value to format.
            expected: The expected OData string representation.
            description: Human-readable description of the test case.
        """
        assert _format_value(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected", "description"),
        [
            (-1, "-1", "negative integer"),
            (0, "0", "zero integer"),
            (1, "1", "positive integer"),
            (42, "42", "two-digit integer"),
            (1000000, "1000000", "large integer"),
            (-1.0, "-1.0", "negative float"),
            (0.0, "0.0", "zero float"),
            (1.0, "1.0", "positive float"),
            (3.14, "3.14", "decimal float"),
            (1e5, "100000.0", "scientific notation float"),
        ],
        ids=lambda x: x if isinstance(x, str) else None,
    )
    def test_formats_numeric_values(self, value, expected: str, description: str) -> None:
        """Validate integer and float value formatting.

        Args:
            value: The numeric value to format.
            expected: The expected OData string representation.
            description: Human-readable description of the test case.
        """
        assert _format_value(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected", "description"),
        [
            ("string", "'string'", "simple string"),
            ("", "''", "empty string"),
            ("hello world", "'hello world'", "string with space"),
            ("it's", "'it''s'", "string with single quote"),
            ("it''s", "'it''''s'", "string with two single quotes"),
            ("'quoted'", "'''quoted'''", "fully quoted string"),
            ("O'Brien", "'O''Brien'", "name with apostrophe"),
        ],
        ids=lambda x: x if isinstance(x, str) and "'" not in x else None,
    )
    def test_formats_string_values_with_quote_escaping(self, value: str, expected: str, description: str) -> None:
        """Validate string value formatting with proper quote escaping.

        Single quotes in strings must be escaped by doubling them in OData.

        Args:
            value: The string value to format.
            expected: The expected OData string representation.
            description: Human-readable description of the test case.
        """
        assert _format_value(value) == expected

    def test_formats_date_values(self) -> None:
        """Validate date value formatting to ISO 8601 date format."""
        test_date = date(2024, 6, 15)
        assert _format_value(test_date) == "2024-06-15"

    def test_formats_datetime_values(self) -> None:
        """Validate datetime value formatting to ISO 8601 datetime format with Z suffix."""
        test_datetime = datetime(2024, 6, 15, 14, 30, 45)
        assert _format_value(test_datetime) == "2024-06-15T14:30:45Z"

    @pytest.mark.parametrize(
        ("value", "description"),
        [
            ([], "empty list"),
            ({}, "empty dict"),
            ((), "empty tuple"),
            (object(), "generic object"),
        ],
        ids=lambda x: x if isinstance(x, str) else None,
    )
    def test_raises_error_for_unsupported_types(self, value, description: str) -> None:
        """Validate that unsupported types raise QueryValidationError in _format_value.

        Args:
            value: The unsupported value to format.
            description: Human-readable description of the test case.
        """
        with pytest.raises(
            QueryValidationError,
            match=(
                f"Cannot format value of type '{type(value).__name__}'. "
                f"Supported types: bool, int, float, str, date, datetime, None"
            ),
        ):
            _format_value(value)


# =============================================================================
# FilterExpression Protocol Tests
# =============================================================================


class TestFilterExpressionProtocol:
    """Test suite for the FilterExpression protocol.

    FilterExpression is a runtime-checkable protocol that requires
    classes to implement the to_odata() -> str method.
    """

    def test_recognizes_conformant_class(self) -> None:
        """Validate that a class implementing to_odata() is recognized as FilterExpression."""

        class CustomFilterExpression:
            def to_odata(self) -> str:
                return "custom_filter()"

        expression = CustomFilterExpression()
        assert isinstance(expression, FilterExpression)
        assert expression.to_odata() == "custom_filter()"

    def test_rejects_non_conformant_class(self) -> None:
        """Validate that a class not implementing to_odata() is not recognized."""

        class NonFilterExpression:
            pass

        assert not isinstance(NonFilterExpression(), FilterExpression)

    def test_rejects_class_with_wrong_method_name(self) -> None:
        """Validate that a class with different method name is not recognized."""

        class WrongMethodName:
            def to_filter(self) -> str:
                return "filter"

        assert not isinstance(WrongMethodName(), FilterExpression)


# =============================================================================
# Comparison Expression Tests
# =============================================================================


class TestComparisonExpression:
    """Test suite for the Comparison expression class.

    Comparison represents a single comparison: <field> <operator> <value>
    Examples: name eq 'John', age gt 18, active eq true
    """

    def test_creates_valid_comparison(self) -> None:
        """Validate that a valid Comparison is created successfully."""
        comparison = Comparison(field="name", operator="eq", value="John")
        assert comparison.field == "name"
        assert comparison.operator == "eq"
        assert comparison.value == "John"

    def test_is_immutable_dataclass(self) -> None:
        """Validate that Comparison is immutable (frozen dataclass)."""
        comparison = Comparison(field="name", operator="eq", value="John")
        with pytest.raises(AttributeError):
            comparison.field = "other_name"

    @pytest.mark.parametrize(
        ("field", "operator", "value", "expected_odata"),
        [
            ("name", "eq", "John", "name eq 'John'"),
            ("age", "gt", 18, "age gt 18"),
            ("price", "le", 99.99, "price le 99.99"),
            ("active", "eq", True, "active eq true"),
            ("deleted", "eq", False, "deleted eq false"),
            ("parent", "eq", None, "parent eq null"),
            ("created", "ge", date(2024, 1, 1), "created ge 2024-01-01"),
        ],
        ids=["string", "integer", "float", "bool_true", "bool_false", "null", "date"],
    )
    def test_generates_correct_odata_filter(self, field: str, operator: str, value, expected_odata: str) -> None:
        """Validate that to_odata() generates correct OData filter strings.

        Args:
            field: The field name.
            operator: The comparison operator.
            value: The value to compare against.
            expected_odata: The expected OData filter string.
        """
        comparison = Comparison(field=field, operator=operator, value=value)
        assert comparison.to_odata() == expected_odata

    def test_rejects_invalid_field_name(self) -> None:
        """Validate that invalid field names are rejected during creation."""
        with pytest.raises(QueryValidationError, match="Field name cannot be empty"):
            Comparison(field="", operator="eq", value="John")

    def test_rejects_invalid_operator(self) -> None:
        """Validate that invalid operators are rejected during creation."""
        with pytest.raises(QueryValidationError, match="Unsupported operator: invalid"):
            Comparison(field="name", operator="invalid", value="John")

    def test_rejects_invalid_value_type(self) -> None:
        """Validate that invalid value types are rejected during creation."""
        with pytest.raises(
            QueryValidationError,
            match="Unsupported value type: 'list'",
        ):
            Comparison(field="name", operator="eq", value=[])


class TestComparisonBooleanOperators:
    """Test suite for Comparison's boolean operator overloads (__and__, __or__)."""

    def test_and_operator_creates_and_expression(self) -> None:
        """Validate that & operator creates an And expression."""
        left = Comparison(field="name", operator="eq", value="John")
        right = Comparison(field="age", operator="gt", value=18)

        result = left & right

        assert isinstance(result, And)
        assert result.expressions == (left, right)

    def test_and_operator_generates_correct_odata(self) -> None:
        """Validate that & operator result generates correct OData string."""
        left = Comparison(field="name", operator="eq", value="John")
        right = Comparison(field="age", operator="gt", value=18)

        result = left & right

        assert result.to_odata() == "(name eq 'John' and age gt 18)"

    def test_or_operator_creates_or_expression(self) -> None:
        """Validate that | operator creates an Or expression."""
        left = Comparison(field="name", operator="eq", value="John")
        right = Comparison(field="name", operator="eq", value="Jane")

        result = left | right

        assert isinstance(result, Or)
        assert result.expressions == (left, right)

    def test_or_operator_generates_correct_odata(self) -> None:
        """Validate that | operator result generates correct OData string."""
        left = Comparison(field="name", operator="eq", value="John")
        right = Comparison(field="name", operator="eq", value="Jane")

        result = left | right

        assert result.to_odata() == "(name eq 'John' or name eq 'Jane')"


# =============================================================================
# InList Expression Tests
# =============================================================================


class TestInListExpression:
    """Test suite for the InList expression class.

    InList represents an IN-style query: field IN (value1, value2, ...)
    Since OData has no native IN operator, this generates OR-chained equalities.
    """

    def test_creates_valid_in_list(self) -> None:
        """Validate that a valid InList is created successfully."""
        in_list = InList(field="status", values=("active", "pending"))
        assert in_list.field == "status"
        assert in_list.values == ("active", "pending")

    def test_is_immutable_dataclass(self) -> None:
        """Validate that InList is immutable (frozen dataclass)."""
        in_list = InList(field="status", values=("active",))
        with pytest.raises(AttributeError):
            in_list.field = "other_status"

    @pytest.mark.parametrize(
        ("field", "values", "expected_odata"),
        [
            ("name", ("John",), "(name eq 'John')"),
            ("name", ("John", "Jane"), "(name eq 'John' or name eq 'Jane')"),
            ("id", (1, 2, 3), "(id eq 1 or id eq 2 or id eq 3)"),
            ("active", (True, False), "(active eq true or active eq false)"),
            ("status", (None, "pending"), "(status eq null or status eq 'pending')"),
        ],
        ids=["single_string", "two_strings", "three_integers", "booleans", "mixed_null"],
    )
    def test_generates_correct_odata_filter(self, field: str, values: tuple, expected_odata: str) -> None:
        """Validate that to_odata() generates correct OData OR-chain.

        Args:
            field: The field name.
            values: Tuple of values to match against.
            expected_odata: The expected OData filter string.
        """
        in_list = InList(field=field, values=values)
        assert in_list.to_odata() == expected_odata

    def test_rejects_invalid_field_name(self) -> None:
        """Validate that invalid field names are rejected during creation."""
        with pytest.raises(QueryValidationError, match="Field name cannot be empty"):
            InList(field="", values=("active",))

    def test_rejects_empty_values_tuple(self) -> None:
        """Validate that empty values tuple is rejected during creation."""
        with pytest.raises(
            QueryValidationError,
            match=(
                r"InList for field 'status' requires at least one value. "
                r"Provide a non-empty tuple of values"
            ),
        ):
            InList(field="status", values=())

    def test_rejects_invalid_value_in_tuple(self) -> None:
        """Validate that invalid value types in tuple are rejected."""
        with pytest.raises(
            QueryValidationError,
            match="Unsupported value type: 'list'",
        ):
            InList(field="name", values=("valid", []))

    def test_accepts_list_as_values_argument(self) -> None:
        """Validate that a list can be passed as values (duck typing)."""
        in_list = InList(field="status", values=["active", "pending"])
        # List works but is stored as-is (not converted to tuple)
        assert in_list.to_odata() == "(status eq 'active' or status eq 'pending')"


class TestInListBooleanOperators:
    """Test suite for InList's boolean operator overloads (__and__, __or__)."""

    def test_and_operator_creates_and_expression(self) -> None:
        """Validate that & operator creates an And expression."""
        left = InList(field="status", values=("active", "pending"))
        right = InList(field="type", values=("user", "admin"))

        result = left & right

        assert isinstance(result, And)
        assert result.expressions == (left, right)

    def test_and_operator_generates_correct_odata(self) -> None:
        """Validate that & operator result generates correct OData string."""
        left = InList(field="status", values=("active", "pending"))
        right = InList(field="type", values=("user", "admin"))

        result = left & right

        expected = "((status eq 'active' or status eq 'pending') and (type eq 'user' or type eq 'admin'))"
        assert result.to_odata() == expected

    def test_or_operator_creates_or_expression(self) -> None:
        """Validate that | operator creates an Or expression."""
        left = InList(field="status", values=("active",))
        right = InList(field="status", values=("pending",))

        result = left | right

        assert isinstance(result, Or)
        assert result.expressions == (left, right)

    def test_or_operator_generates_correct_odata(self) -> None:
        """Validate that | operator result generates correct OData string."""
        left = InList(field="status", values=("active",))
        right = InList(field="status", values=("pending",))

        result = left | right

        expected = "((status eq 'active') or (status eq 'pending'))"
        assert result.to_odata() == expected


# =============================================================================
# Raw Expression Tests
# =============================================================================


class TestRawExpression:
    """Test suite for the Raw expression class.

    Raw is an escape hatch for OData syntax not supported by typed expressions.
    The expression is passed through without validation or modification.
    """

    def test_creates_valid_raw_expression(self) -> None:
        """Validate that a valid Raw expression is created successfully."""
        raw = Raw(expression="contains(name, 'John')")
        assert raw.expression == "contains(name, 'John')"

    def test_is_immutable_dataclass(self) -> None:
        """Validate that Raw is immutable (frozen dataclass)."""
        raw = Raw(expression="contains(name, 'John')")
        with pytest.raises(AttributeError):
            raw.expression = "other expression"

    @pytest.mark.parametrize(
        ("expression", "description"),
        [
            ("contains(name, 'John')", "contains function"),
            ("startswith(email, 'admin')", "startswith function"),
            ("endswith(url, '.com')", "endswith function"),
            ("length(name) gt 10", "length function"),
            ("year(created) eq 2024", "year function"),
            ("tolower(name) eq 'john'", "tolower function"),
            ("concat(firstName, lastName)", "concat function"),
            ("not (active eq true)", "negation expression"),
        ],
        ids=lambda x: x if isinstance(x, str) and len(x) < 30 else None,
    )
    def test_passes_expression_through_unchanged(self, expression: str, description: str) -> None:
        """Validate that to_odata() returns the expression unchanged.

        Args:
            expression: The raw OData expression.
            description: Human-readable description of the test case.
        """
        raw = Raw(expression=expression)
        assert raw.to_odata() == expression

    @pytest.mark.parametrize(
        "expression",
        ["", "   ", "\t", "\n"],
        ids=["empty", "spaces", "tab", "newline"],
    )
    def test_rejects_empty_or_whitespace_expression(self, expression: str) -> None:
        """Validate that empty or whitespace-only expressions are rejected.

        Args:
            expression: The invalid expression to validate.
        """
        with pytest.raises(
            QueryValidationError,
            match=(
                r"Raw expression cannot be empty or whitespace-only. "
                r"Provide a valid OData filter expression string"
            ),
        ):
            Raw(expression=expression)


class TestRawBooleanOperators:
    """Test suite for Raw's boolean operator overloads (__and__, __or__)."""

    def test_and_operator_creates_and_expression(self) -> None:
        """Validate that & operator creates an And expression."""
        left = Raw(expression="contains(name, 'John')")
        right = Raw(expression="age gt 18")

        result = left & right

        assert isinstance(result, And)
        assert result.expressions == (left, right)

    def test_and_operator_generates_correct_odata(self) -> None:
        """Validate that & operator result generates correct OData string."""
        left = Raw(expression="contains(name, 'John')")
        right = Raw(expression="age gt 18")

        result = left & right

        assert result.to_odata() == "(contains(name, 'John') and age gt 18)"

    def test_or_operator_creates_or_expression(self) -> None:
        """Validate that | operator creates an Or expression."""
        left = Raw(expression="contains(name, 'John')")
        right = Raw(expression="contains(name, 'Jane')")

        result = left | right

        assert isinstance(result, Or)
        assert result.expressions == (left, right)

    def test_or_operator_generates_correct_odata(self) -> None:
        """Validate that | operator result generates correct OData string."""
        left = Raw(expression="contains(name, 'John')")
        right = Raw(expression="contains(name, 'Jane')")

        result = left | right

        assert result.to_odata() == "(contains(name, 'John') or contains(name, 'Jane'))"


# =============================================================================
# And Expression Tests
# =============================================================================


class TestAndExpression:
    """Test suite for the And expression class.

    And combines two or more expressions with OData 'and' operator.
    It is typically created using the & operator on expressions.
    """

    def test_creates_valid_and_expression(self) -> None:
        """Validate that a valid And expression is created successfully."""
        left = Comparison(field="name", operator="eq", value="John")
        right = Comparison(field="age", operator="gt", value=18)

        and_expr = And(expressions=(left, right))

        assert and_expr.expressions == (left, right)

    def test_is_immutable_dataclass(self) -> None:
        """Validate that And is immutable (frozen dataclass)."""
        left = Comparison(field="name", operator="eq", value="John")
        right = Comparison(field="age", operator="gt", value=18)
        and_expr = And(expressions=(left, right))

        with pytest.raises(AttributeError):
            and_expr.expressions = ()

    def test_generates_correct_odata_with_two_expressions(self) -> None:
        """Validate OData generation with two expressions."""
        and_expr = And(
            expressions=(
                Comparison(field="name", operator="eq", value="John"),
                Comparison(field="age", operator="gt", value=18),
            )
        )
        assert and_expr.to_odata() == "(name eq 'John' and age gt 18)"

    def test_generates_correct_odata_with_three_expressions(self) -> None:
        """Validate OData generation with three expressions."""
        and_expr = And(
            expressions=(
                Comparison(field="name", operator="eq", value="John"),
                Comparison(field="age", operator="gt", value=18),
                Comparison(field="active", operator="eq", value=True),
            )
        )
        assert and_expr.to_odata() == "(name eq 'John' and age gt 18 and active eq true)"

    def test_works_with_mixed_expression_types(self) -> None:
        """Validate And works with Comparison, InList, and Raw expressions."""
        and_expr = And(
            expressions=(
                Comparison(field="name", operator="eq", value="John"),
                Raw(expression="contains(email, '@example.com')"),
            )
        )
        assert and_expr.to_odata() == "(name eq 'John' and contains(email, '@example.com'))"


class TestAndValidation:
    """Test suite for And expression validation."""

    def test_rejects_non_tuple_argument(self) -> None:
        """Validate that passing a single expression (not tuple) is rejected."""
        comparison = Comparison(field="name", operator="eq", value="John")

        with pytest.raises(
            QueryValidationError,
            match=f"And expression requires a tuple of expressions, got {type(comparison)}",
        ):
            And(expressions=comparison)

    def test_rejects_single_expression_tuple(self) -> None:
        """Validate that a tuple with only one expression is rejected."""
        comparison = Comparison(field="name", operator="eq", value="John")

        with pytest.raises(
            QueryValidationError,
            match="And expression requires at least two expressions, got 1",
        ):
            And(expressions=(comparison,))

    def test_rejects_empty_tuple(self) -> None:
        """Validate that an empty tuple is rejected."""
        with pytest.raises(
            QueryValidationError,
            match="And expression requires at least two expressions, got 0",
        ):
            And(expressions=())

    def test_rejects_non_filter_expression_item(self) -> None:
        """Validate that non-FilterExpression items are rejected with index info."""
        comparison = Comparison(field="name", operator="eq", value="John")
        invalid_item = "This is not a FilterExpression"

        with pytest.raises(
            QueryValidationError,
            match=(f"And expression item at index 1 must implement FilterExpression, got {type(invalid_item)}"),
        ):
            And(expressions=(comparison, invalid_item))


class TestAndBooleanOperators:
    """Test suite for And's boolean operator overloads (__and__, __or__)."""

    def test_and_operator_extends_expressions(self) -> None:
        """Validate that & operator extends the And expression (flattening)."""
        expr_a = Comparison(field="name", operator="eq", value="John")
        expr_b = Comparison(field="age", operator="gt", value=18)
        expr_c = Comparison(field="active", operator="eq", value=True)

        and_expr = And(expressions=(expr_a, expr_b))
        result = and_expr & expr_c

        assert isinstance(result, And)
        assert result.expressions == (expr_a, expr_b, expr_c)
        assert result.to_odata() == "(name eq 'John' and age gt 18 and active eq true)"

    def test_or_operator_creates_or_expression(self) -> None:
        """Validate that | operator creates an Or containing the And."""
        expr_a = Comparison(field="name", operator="eq", value="John")
        expr_b = Comparison(field="age", operator="gt", value=18)
        expr_c = Comparison(field="status", operator="eq", value="vip")

        and_expr = And(expressions=(expr_a, expr_b))
        result = and_expr | expr_c

        assert isinstance(result, Or)
        assert result.expressions == (and_expr, expr_c)
        assert result.to_odata() == "((name eq 'John' and age gt 18) or status eq 'vip')"


# =============================================================================
# Or Expression Tests
# =============================================================================


class TestOrExpression:
    """Test suite for the Or expression class.

    Or combines two or more expressions with OData 'or' operator.
    It is typically created using the | operator on expressions.
    """

    def test_creates_valid_or_expression(self) -> None:
        """Validate that a valid Or expression is created successfully."""
        left = Comparison(field="status", operator="eq", value="active")
        right = Comparison(field="status", operator="eq", value="pending")

        or_expr = Or(expressions=(left, right))

        assert or_expr.expressions == (left, right)

    def test_is_immutable_dataclass(self) -> None:
        """Validate that Or is immutable (frozen dataclass)."""
        left = Comparison(field="status", operator="eq", value="active")
        right = Comparison(field="status", operator="eq", value="pending")
        or_expr = Or(expressions=(left, right))

        with pytest.raises(AttributeError):
            or_expr.expressions = ()

    def test_generates_correct_odata_with_two_expressions(self) -> None:
        """Validate OData generation with two expressions."""
        or_expr = Or(
            expressions=(
                Comparison(field="status", operator="eq", value="active"),
                Comparison(field="status", operator="eq", value="pending"),
            )
        )
        assert or_expr.to_odata() == "(status eq 'active' or status eq 'pending')"

    def test_generates_correct_odata_with_three_expressions(self) -> None:
        """Validate OData generation with three expressions."""
        or_expr = Or(
            expressions=(
                Comparison(field="status", operator="eq", value="active"),
                Comparison(field="status", operator="eq", value="pending"),
                Comparison(field="status", operator="eq", value="archived"),
            )
        )
        assert or_expr.to_odata() == "(status eq 'active' or status eq 'pending' or status eq 'archived')"

    def test_works_with_mixed_expression_types(self) -> None:
        """Validate Or works with Comparison, InList, and Raw expressions."""
        or_expr = Or(
            expressions=(
                Comparison(field="role", operator="eq", value="admin"),
                Raw(expression="startswith(email, 'super')"),
            )
        )
        assert or_expr.to_odata() == "(role eq 'admin' or startswith(email, 'super'))"


class TestOrValidation:
    """Test suite for Or expression validation."""

    def test_rejects_non_tuple_argument(self) -> None:
        """Validate that passing a single expression (not tuple) is rejected."""
        comparison = Comparison(field="name", operator="eq", value="John")

        with pytest.raises(
            QueryValidationError,
            match=f"Or expression requires a tuple of expressions, got {type(comparison).__name__}",
        ):
            Or(expressions=comparison)

    def test_rejects_single_expression_tuple(self) -> None:
        """Validate that a tuple with only one expression is rejected."""
        comparison = Comparison(field="name", operator="eq", value="John")

        with pytest.raises(
            QueryValidationError,
            match="Or expression requires at least two expressions, got 1",
        ):
            Or(expressions=(comparison,))

    def test_rejects_empty_tuple(self) -> None:
        """Validate that an empty tuple is rejected."""
        with pytest.raises(
            QueryValidationError,
            match="Or expression requires at least two expressions, got 0",
        ):
            Or(expressions=())

    def test_rejects_non_filter_expression_item(self) -> None:
        """Validate that non-FilterExpression items are rejected with index info."""
        comparison = Comparison(field="name", operator="eq", value="John")
        invalid_item = "This is not a FilterExpression"

        with pytest.raises(
            QueryValidationError,
            match=(f"Or expression item at index 1 must implement FilterExpression, got {type(invalid_item).__name__}"),
        ):
            Or(expressions=(comparison, invalid_item))


class TestOrBooleanOperators:
    """Test suite for Or's boolean operator overloads (__and__, __or__)."""

    def test_or_operator_extends_expressions(self) -> None:
        """Validate that | operator extends the Or expression (flattening)."""
        expr_a = Comparison(field="status", operator="eq", value="active")
        expr_b = Comparison(field="status", operator="eq", value="pending")
        expr_c = Comparison(field="status", operator="eq", value="archived")

        or_expr = Or(expressions=(expr_a, expr_b))
        result = or_expr | expr_c

        assert isinstance(result, Or)
        assert result.expressions == (expr_a, expr_b, expr_c)
        assert result.to_odata() == "(status eq 'active' or status eq 'pending' or status eq 'archived')"

    def test_and_operator_creates_and_expression(self) -> None:
        """Validate that & operator creates an And containing the Or."""
        expr_a = Comparison(field="status", operator="eq", value="active")
        expr_b = Comparison(field="status", operator="eq", value="pending")
        expr_c = Comparison(field="verified", operator="eq", value=True)

        or_expr = Or(expressions=(expr_a, expr_b))
        result = or_expr & expr_c

        assert isinstance(result, And)
        assert result.expressions == (or_expr, expr_c)
        assert result.to_odata() == "((status eq 'active' or status eq 'pending') and verified eq true)"


# =============================================================================
# Complex Expression Chaining Tests
# =============================================================================


class TestComplexExpressionChaining:
    """Test suite for complex expression chaining scenarios.

    Tests combinations of multiple operators and expression types to verify
    correct precedence and OData output generation.
    """

    def test_chains_multiple_and_operations(self) -> None:
        """Validate chaining multiple & operations."""
        expr_a = Comparison(field="a", operator="eq", value=1)
        expr_b = Comparison(field="b", operator="eq", value=2)
        expr_c = Comparison(field="c", operator="eq", value=3)
        expr_d = Comparison(field="d", operator="eq", value=4)

        result = expr_a & expr_b & expr_c & expr_d

        assert result.to_odata() == "(a eq 1 and b eq 2 and c eq 3 and d eq 4)"

    def test_chains_multiple_or_operations(self) -> None:
        """Validate chaining multiple | operations."""
        expr_a = Comparison(field="status", operator="eq", value="a")
        expr_b = Comparison(field="status", operator="eq", value="b")
        expr_c = Comparison(field="status", operator="eq", value="c")
        expr_d = Comparison(field="status", operator="eq", value="d")

        result = expr_a | expr_b | expr_c | expr_d

        assert result.to_odata() == "(status eq 'a' or status eq 'b' or status eq 'c' or status eq 'd')"

    def test_mixed_and_or_with_parentheses(self) -> None:
        """Validate mixed AND/OR operations maintain correct structure."""
        # (A AND B) OR C
        expr_a = Comparison(field="name", operator="eq", value="John")
        expr_b = Comparison(field="age", operator="gt", value=18)
        expr_c = Comparison(field="vip", operator="eq", value=True)

        result = (expr_a & expr_b) | expr_c

        assert result.to_odata() == "((name eq 'John' and age gt 18) or vip eq true)"

    def test_or_then_and(self) -> None:
        """Validate OR followed by AND maintains correct structure."""
        # (A OR B) AND C
        expr_a = Comparison(field="status", operator="eq", value="active")
        expr_b = Comparison(field="status", operator="eq", value="pending")
        expr_c = Comparison(field="verified", operator="eq", value=True)

        result = (expr_a | expr_b) & expr_c

        assert result.to_odata() == "((status eq 'active' or status eq 'pending') and verified eq true)"

    def test_complex_nested_expression(self) -> None:
        """Validate complex nested expressions."""
        # (A AND B) OR (C AND D)
        expr_a = Comparison(field="type", operator="eq", value="user")
        expr_b = Comparison(field="active", operator="eq", value=True)
        expr_c = Comparison(field="type", operator="eq", value="admin")
        expr_d = Comparison(field="superuser", operator="eq", value=True)

        left = expr_a & expr_b
        right = expr_c & expr_d
        result = left | right

        assert result.to_odata() == "((type eq 'user' and active eq true) or (type eq 'admin' and superuser eq true))"

    def test_raw_mixed_with_typed_expressions(self) -> None:
        """Validate Raw expressions work in complex chains."""
        comparison = Comparison(field="active", operator="eq", value=True)
        raw = Raw(expression="contains(name, 'admin')")
        in_list = InList(field="role", values=("manager", "director"))

        result = comparison & raw & in_list

        assert result.to_odata() == (
            "(active eq true and contains(name, 'admin') and (role eq 'manager' or role eq 'director'))"
        )
