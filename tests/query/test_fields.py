"""Tests for Field accessor and F factory for building OData filter expressions.

This module provides comprehensive tests for the odyn.query.fields module,
covering the Field class, _FieldFactory class, and the F singleton.

Test Categories:
    - Field class: creation, immutability, hashing, comparison operators
    - Comparison operators: __eq__, __ne__, __gt__, __ge__, __lt__, __le__
    - is_in method: for IN-style queries
    - F factory: attribute access for field creation
    - Field validation: invalid field name handling
"""

from datetime import date, datetime

import pytest

from odyn.exceptions import QueryValidationError
from odyn.query.expressions import And, Comparison, InList, Or
from odyn.query.fields import F, F as F1, F as F2, Field

__all__ = []


# =============================================================================
# Field Creation Tests
# =============================================================================


class TestFieldCreation:
    """Test suite for Field class creation and basic attributes.

    Field is a frozen dataclass representing a field reference.
    It is created via the F factory: F.FieldName
    """

    def test_creates_valid_field(self) -> None:
        """Validate that a valid Field is created successfully."""
        field = Field(name="CustomerName")
        assert field.name == "CustomerName"

    def test_creates_field_with_underscores(self) -> None:
        """Validate that fields with underscores are accepted."""
        field = Field(name="Posting_Date")
        assert field.name == "Posting_Date"

    def test_creates_field_with_numbers(self) -> None:
        """Validate that fields with numbers are accepted."""
        field = Field(name="Address2")
        assert field.name == "Address2"

    def test_is_immutable_dataclass(self) -> None:
        """Validate that Field is immutable (frozen dataclass)."""
        field = Field(name="Status")
        with pytest.raises(AttributeError):
            field.name = "OtherStatus"

    def test_has_slots(self) -> None:
        """Validate that Field uses slots for memory efficiency."""
        field = Field(name="Status")
        # Frozen dataclass with slots raises TypeError when trying to set new attributes
        with pytest.raises((AttributeError, TypeError)):
            field.some_new_attribute = "value"


# =============================================================================
# Field Hash Tests
# =============================================================================


class TestFieldHashing:
    """Test suite for Field hashing behavior.

    Field must be hashable to be usable in sets and as dict keys.
    Since __eq__ is overridden for OData comparison building, we need
    an explicit __hash__ implementation.
    """

    def test_field_is_hashable(self) -> None:
        """Validate that Field instances can be hashed."""
        field = Field(name="Status")
        # Should not raise
        hash_value = hash(field)
        assert isinstance(hash_value, int)

    def test_fields_with_same_name_have_same_hash(self) -> None:
        """Validate that two fields with the same name have the same hash."""
        field1 = Field(name="Status")
        field2 = Field(name="Status")
        assert hash(field1) == hash(field2)

    def test_fields_with_different_names_have_different_hash(self) -> None:
        """Validate that two fields with different names have different hashes."""
        field1 = Field(name="Status")
        field2 = Field(name="Type")
        # While not guaranteed by the hash contract, this is extremely likely
        assert hash(field1) != hash(field2)

    def test_field_can_be_added_to_set(self) -> None:
        """Validate that Field instances can be added to a set.

        Note: Since __eq__ returns a Comparison (not bool), set deduplication
        works by identity and hash. Two fields with the same name have the same
        hash but __eq__ doesn't return True/False, so Python falls back to
        identity comparison. Thus field1 and field3 are treated as separate.
        """
        field1 = Field(name="Status")
        field2 = Field(name="Type")

        # Simply verify fields can be added to a set without error
        field_set = {field1, field2}
        assert len(field_set) == 2
        assert field1 in field_set
        assert field2 in field_set

    def test_field_can_be_dict_key(self) -> None:
        """Validate that Field instances can be used as dict keys."""
        field = Field(name="Status")
        field_dict = {field: "some_value"}
        assert field_dict[field] == "some_value"


# =============================================================================
# Field Repr Tests
# =============================================================================


class TestFieldRepr:
    """Test suite for Field string representation."""

    def test_repr_shows_f_prefix(self) -> None:
        """Validate that repr uses F.FieldName format."""
        field = Field(name="Status")
        assert repr(field) == "F.Status"

    def test_repr_with_underscore_field(self) -> None:
        """Validate repr with underscore in field name."""
        field = Field(name="Posting_Date")
        assert repr(field) == "F.Posting_Date"


# =============================================================================
# Field Validation Tests
# =============================================================================


class TestFieldValidation:
    """Test suite for Field name validation.

    Field names are validated during __post_init__ using
    the _validate_field_name function from expressions module.
    """

    def test_rejects_empty_field_name(self) -> None:
        """Validate that empty field names are rejected."""
        with pytest.raises(QueryValidationError, match="Field name cannot be empty"):
            Field(name="")

    def test_rejects_field_name_starting_with_number(self) -> None:
        """Validate that field names starting with numbers are rejected."""
        with pytest.raises(
            QueryValidationError,
            match="Invalid field name '123Field': must start with a letter or underscore",
        ):
            Field(name="123Field")

    def test_rejects_field_name_with_special_characters(self) -> None:
        """Validate that field names with special characters are rejected."""
        with pytest.raises(
            QueryValidationError,
            match="Invalid field name 'Field-Name': can only contain alphanumeric characters and underscores",
        ):
            Field(name="Field-Name")

    def test_rejects_field_name_with_spaces(self) -> None:
        """Validate that field names with spaces are rejected."""
        with pytest.raises(
            QueryValidationError,
            match="Invalid field name 'Field Name': can only contain alphanumeric characters and underscores",
        ):
            Field(name="Field Name")


# =============================================================================
# Field Comparison Operator Tests
# =============================================================================


class TestFieldEqualityOperator:
    """Test suite for Field.__eq__ operator (==).

    Note: __eq__ returns a Comparison, not a bool. This is an intentional
    design for building OData filter expressions.
    """

    def test_eq_returns_comparison(self) -> None:
        """Validate that == returns a Comparison object."""
        field = Field(name="Status")
        result = field == "Active"
        assert isinstance(result, Comparison)

    def test_eq_creates_correct_comparison(self) -> None:
        """Validate that == creates a Comparison with 'eq' operator."""
        field = Field(name="Status")
        result = field == "Active"
        assert result.field == "Status"
        assert result.operator == "eq"
        assert result.value == "Active"

    @pytest.mark.parametrize(
        ("value", "expected_odata"),
        [
            ("Active", "Status eq 'Active'"),
            (123, "Status eq 123"),
            (3.14, "Status eq 3.14"),
            (True, "Status eq true"),
            (False, "Status eq false"),
            (None, "Status eq null"),
            (date(2024, 1, 15), "Status eq 2024-01-15"),
            (datetime(2024, 1, 15, 14, 30, 0), "Status eq 2024-01-15T14:30:00Z"),
        ],
        ids=["string", "integer", "float", "true", "false", "null", "date", "datetime"],
    )
    def test_eq_with_all_value_types(self, value, expected_odata: str) -> None:
        """Validate that == works with all supported value types.

        Args:
            value: The value to compare.
            expected_odata: Expected OData filter string.
        """
        field = Field(name="Status")
        result = field == value
        assert result.to_odata() == expected_odata


class TestFieldInequalityOperator:
    """Test suite for Field.__ne__ operator (!=)."""

    def test_ne_returns_comparison(self) -> None:
        """Validate that != returns a Comparison object."""
        field = Field(name="Status")
        result = field != "Inactive"
        assert isinstance(result, Comparison)

    def test_ne_creates_correct_comparison(self) -> None:
        """Validate that != creates a Comparison with 'ne' operator."""
        field = Field(name="Status")
        result = field != "Inactive"
        assert result.field == "Status"
        assert result.operator == "ne"
        assert result.value == "Inactive"

    def test_ne_generates_correct_odata(self) -> None:
        """Validate that != generates correct OData filter string."""
        field = Field(name="Status")
        result = field != "Inactive"
        assert result.to_odata() == "Status ne 'Inactive'"


class TestFieldGreaterThanOperator:
    """Test suite for Field.__gt__ operator (>)."""

    def test_gt_returns_comparison(self) -> None:
        """Validate that > returns a Comparison object."""
        field = Field(name="Balance")
        result = field > 1000
        assert isinstance(result, Comparison)

    def test_gt_creates_correct_comparison(self) -> None:
        """Validate that > creates a Comparison with 'gt' operator."""
        field = Field(name="Balance")
        result = field > 1000
        assert result.field == "Balance"
        assert result.operator == "gt"
        assert result.value == 1000

    @pytest.mark.parametrize(
        ("value", "expected_odata"),
        [
            (100, "Balance gt 100"),
            (99.99, "Balance gt 99.99"),
            (date(2024, 1, 1), "Balance gt 2024-01-01"),
        ],
        ids=["integer", "float", "date"],
    )
    def test_gt_generates_correct_odata(self, value, expected_odata: str) -> None:
        """Validate that > generates correct OData filter string.

        Args:
            value: The value to compare.
            expected_odata: Expected OData filter string.
        """
        field = Field(name="Balance")
        result = field > value
        assert result.to_odata() == expected_odata


class TestFieldGreaterOrEqualOperator:
    """Test suite for Field.__ge__ operator (>=)."""

    def test_ge_returns_comparison(self) -> None:
        """Validate that >= returns a Comparison object."""
        field = Field(name="Age")
        result = field >= 18
        assert isinstance(result, Comparison)

    def test_ge_creates_correct_comparison(self) -> None:
        """Validate that >= creates a Comparison with 'ge' operator."""
        field = Field(name="Age")
        result = field >= 18
        assert result.field == "Age"
        assert result.operator == "ge"
        assert result.value == 18

    def test_ge_generates_correct_odata(self) -> None:
        """Validate that >= generates correct OData filter string."""
        field = Field(name="Age")
        result = field >= 18
        assert result.to_odata() == "Age ge 18"


class TestFieldLessThanOperator:
    """Test suite for Field.__lt__ operator (<)."""

    def test_lt_returns_comparison(self) -> None:
        """Validate that < returns a Comparison object."""
        field = Field(name="Price")
        result = field < 50
        assert isinstance(result, Comparison)

    def test_lt_creates_correct_comparison(self) -> None:
        """Validate that < creates a Comparison with 'lt' operator."""
        field = Field(name="Price")
        result = field < 50
        assert result.field == "Price"
        assert result.operator == "lt"
        assert result.value == 50

    def test_lt_generates_correct_odata(self) -> None:
        """Validate that < generates correct OData filter string."""
        field = Field(name="Price")
        result = field < 50
        assert result.to_odata() == "Price lt 50"


class TestFieldLessOrEqualOperator:
    """Test suite for Field.__le__ operator (<=)."""

    def test_le_returns_comparison(self) -> None:
        """Validate that <= returns a Comparison object."""
        field = Field(name="Quantity")
        result = field <= 100
        assert isinstance(result, Comparison)

    def test_le_creates_correct_comparison(self) -> None:
        """Validate that <= creates a Comparison with 'le' operator."""
        field = Field(name="Quantity")
        result = field <= 100
        assert result.field == "Quantity"
        assert result.operator == "le"
        assert result.value == 100

    def test_le_generates_correct_odata(self) -> None:
        """Validate that <= generates correct OData filter string."""
        field = Field(name="Quantity")
        result = field <= 100
        assert result.to_odata() == "Quantity le 100"


# =============================================================================
# Field is_in Method Tests
# =============================================================================


class TestFieldIsInMethod:
    """Test suite for Field.is_in() method.

    is_in creates an InList expression for IN-style queries.
    """

    def test_is_in_returns_inlist(self) -> None:
        """Validate that is_in returns an InList object."""
        field = Field(name="Type")
        result = field.is_in(["Sale", "Purchase"])
        assert isinstance(result, InList)

    def test_is_in_creates_correct_inlist(self) -> None:
        """Validate that is_in creates InList with correct field and values."""
        field = Field(name="Type")
        result = field.is_in(["Sale", "Purchase"])
        assert result.field == "Type"
        assert result.values == ("Sale", "Purchase")

    @pytest.mark.parametrize(
        ("values", "expected_odata"),
        [
            (["Active"], "(Status eq 'Active')"),
            (["Active", "Pending"], "(Status eq 'Active' or Status eq 'Pending')"),
            ([1, 2, 3], "(Status eq 1 or Status eq 2 or Status eq 3)"),
            ([True, False], "(Status eq true or Status eq false)"),
        ],
        ids=["single_value", "two_values", "integers", "booleans"],
    )
    def test_is_in_generates_correct_odata(self, values: list, expected_odata: str) -> None:
        """Validate that is_in generates correct OData filter string.

        Args:
            values: List of values for the IN expression.
            expected_odata: Expected OData filter string.
        """
        field = Field(name="Status")
        result = field.is_in(values)
        assert result.to_odata() == expected_odata


# =============================================================================
# F Factory Tests
# =============================================================================


class TestFieldFactory:
    """Test suite for the F field factory singleton.

    F is a factory that creates Field instances via attribute access.
    Example: F.Status creates Field(name="Status")
    """

    def test_creates_field_via_attribute_access(self) -> None:
        """Validate that F.FieldName creates a Field instance."""
        field = F.Status
        assert isinstance(field, Field)
        assert field.name == "Status"

    def test_creates_different_fields(self) -> None:
        """Validate that F creates distinct Field instances for different names."""
        field1 = F.Status
        field2 = F.Type
        assert field1.name == "Status"
        assert field2.name == "Type"

    def test_factory_repr(self) -> None:
        """Validate that F factory has correct repr."""
        assert repr(F) == "F"

    def test_creates_field_with_underscores(self) -> None:
        """Validate that F.Field_Name works with underscores."""
        field = F.Posting_Date
        assert field.name == "Posting_Date"

    def test_creates_field_with_numbers(self) -> None:
        """Validate that F works with numbers in field names."""
        field = F.Address2
        assert field.name == "Address2"


class TestFieldFactoryChaining:
    """Test suite for using F factory in expression chains."""

    def test_f_eq_creates_comparison(self) -> None:
        """Validate F.Field == value creates Comparison."""
        result = F.Status == "Active"
        assert isinstance(result, Comparison)
        assert result.to_odata() == "Status eq 'Active'"

    def test_f_ne_creates_comparison(self) -> None:
        """Validate F.Field != value creates Comparison."""
        result = F.Status != "Inactive"
        assert result.to_odata() == "Status ne 'Inactive'"

    def test_f_gt_creates_comparison(self) -> None:
        """Validate F.Field > value creates Comparison."""
        result = F.Balance > 1000
        assert result.to_odata() == "Balance gt 1000"

    def test_f_ge_creates_comparison(self) -> None:
        """Validate F.Field >= value creates Comparison."""
        result = F.Age >= 18
        assert result.to_odata() == "Age ge 18"

    def test_f_lt_creates_comparison(self) -> None:
        """Validate F.Field < value creates Comparison."""
        result = F.Price < 50
        assert result.to_odata() == "Price lt 50"

    def test_f_le_creates_comparison(self) -> None:
        """Validate F.Field <= value creates Comparison."""
        result = F.Quantity <= 100
        assert result.to_odata() == "Quantity le 100"

    def test_f_is_in_creates_inlist(self) -> None:
        """Validate F.Field.is_in() creates InList."""
        result = F.Type.is_in(["Sale", "Purchase"])
        assert isinstance(result, InList)
        assert result.to_odata() == "(Type eq 'Sale' or Type eq 'Purchase')"


# =============================================================================
# Complex Expression Building with F Factory Tests
# =============================================================================


class TestFieldComplexExpressions:
    """Test suite for building complex expressions using F factory.

    Tests combining multiple Field comparisons with AND/OR operators.
    """

    def test_and_operator_with_two_fields(self) -> None:
        """Validate & operator combines two field comparisons."""
        result = (F.Status == "Active") & (F.Type == "Sale")
        assert isinstance(result, And)
        assert result.to_odata() == "(Status eq 'Active' and Type eq 'Sale')"

    def test_or_operator_with_two_fields(self) -> None:
        """Validate | operator combines two field comparisons."""
        result = (F.Status == "Active") | (F.Status == "Pending")
        assert isinstance(result, Or)
        assert result.to_odata() == "(Status eq 'Active' or Status eq 'Pending')"

    def test_chained_and_operators(self) -> None:
        """Validate chaining multiple & operators."""
        result = (F.Status == "Active") & (F.Type == "Sale") & (F.Amount > 100)
        assert result.to_odata() == "(Status eq 'Active' and Type eq 'Sale' and Amount gt 100)"

    def test_chained_or_operators(self) -> None:
        """Validate chaining multiple | operators."""
        result = (F.Status == "A") | (F.Status == "B") | (F.Status == "C")
        assert result.to_odata() == "(Status eq 'A' or Status eq 'B' or Status eq 'C')"

    def test_mixed_and_or_operators(self) -> None:
        """Validate complex AND/OR combination."""
        # (Status == 'Active' AND Amount > 100) OR (VIP == True)
        result = ((F.Status == "Active") & (F.Amount > 100)) | (F.VIP == True)  # noqa: E712
        expected = "((Status eq 'Active' and Amount gt 100) or VIP eq true)"
        assert result.to_odata() == expected

    def test_is_in_combined_with_comparison(self) -> None:
        """Validate is_in combined with regular comparison."""
        result = F.Type.is_in(["Sale", "Purchase"]) & (F.Amount > 500)
        expected = "((Type eq 'Sale' or Type eq 'Purchase') and Amount gt 500)"
        assert result.to_odata() == expected

    def test_multiple_fields_complex_expression(self) -> None:
        """Validate complex expression with multiple different fields."""
        # Active customers with high balance OR VIP status
        result = ((F.CustomerStatus == "Active") & (F.Balance > 10000)) | (F.VIPLevel >= 3)

        expected = "((CustomerStatus eq 'Active' and Balance gt 10000) or VIPLevel ge 3)"
        assert result.to_odata() == expected

    def test_date_range_filter(self) -> None:
        """Validate creating a date range filter with F."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)

        result = (F.PostingDate >= start_date) & (F.PostingDate <= end_date)
        expected = "(PostingDate ge 2024-01-01 and PostingDate le 2024-12-31)"
        assert result.to_odata() == expected


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestFieldEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_single_character_field_name(self) -> None:
        """Validate single character field names work."""
        field = Field(name="x")
        result = field == 1
        assert result.to_odata() == "x eq 1"

    def test_underscore_only_field_name(self) -> None:
        """Validate underscore-only field name works."""
        field = Field(name="_")
        result = field == "value"
        assert result.to_odata() == "_ eq 'value'"

    def test_uppercase_field_name(self) -> None:
        """Validate uppercase field names work."""
        field = Field(name="CUSTOMERID")
        result = field == 123
        assert result.to_odata() == "CUSTOMERID eq 123"

    def test_mixed_case_field_name(self) -> None:
        """Validate mixed case (camelCase) field names work."""
        field = Field(name="customerId")
        result = field == 123
        assert result.to_odata() == "customerId eq 123"

    def test_f_factory_is_singleton_like(self) -> None:
        """Validate F is consistently the same factory instance."""

        assert F1 is F2

    def test_comparison_with_empty_string(self) -> None:
        """Validate comparison with empty string works."""
        result = F.Name == ""
        assert result.to_odata() == "Name eq ''"

    def test_comparison_with_string_containing_quotes(self) -> None:
        """Validate string with quotes is properly escaped."""
        result = F.Name == "O'Brien"
        assert result.to_odata() == "Name eq 'O''Brien'"

    def test_is_in_with_single_value(self) -> None:
        """Validate is_in works with single value list."""
        result = F.Status.is_in(["Active"])
        assert result.to_odata() == "(Status eq 'Active')"
