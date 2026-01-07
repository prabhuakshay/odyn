"""Tests for OData query builder.

This module provides comprehensive tests for the odyn.query.builder module,
covering the ODataQuery class and all its methods for building OData query
parameter dictionaries.

Test Categories:
    - ODataQuery class: creation, dataclass properties
    - select() method: field selection, validation, chaining
    - filter() method: typed filter expressions, type checking
    - filter_raw() method: raw OData filter strings
    - expand() method: entity expansion, validation
    - order_by() method: ordering, validation
    - top() method: result limiting, validation
    - skip() method: pagination, validation
    - count() method: including total count
    - build() method: generating query parameter dictionaries
    - Method chaining: fluent API composition
    - Complex queries: real-world usage patterns
"""

from dataclasses import is_dataclass
from datetime import date, datetime

import pytest

from odyn.exceptions import QueryValidationError
from odyn.query.builder import ODataQuery
from odyn.query.expressions import Comparison, InList, Raw
from odyn.query.fields import F

__all__ = []


# =============================================================================
# ODataQuery Creation Tests
# =============================================================================


class TestODataQueryCreation:
    """Test suite for ODataQuery class creation and basic properties.

    ODataQuery is a dataclass with internal fields for storing query parameters.
    """

    def test_creates_empty_query(self) -> None:
        """Validate that an empty ODataQuery is created with default values."""
        query = ODataQuery()
        assert query._select == []
        assert query._filters == []
        assert query._expand == []
        assert query._order_by == []
        assert query._top is None
        assert query._skip is None
        assert query._count is False

    def test_empty_query_builds_empty_dict(self) -> None:
        """Validate that an empty query builds to an empty dictionary."""
        query = ODataQuery()
        result = query.build()
        assert result == {}

    def test_is_dataclass(self) -> None:
        """Validate that ODataQuery is a dataclass."""

        assert is_dataclass(ODataQuery)


# =============================================================================
# Select Method Tests
# =============================================================================


class TestSelectMethod:
    """Test suite for ODataQuery.select() method.

    select() specifies which fields to include in the response.
    """

    def test_select_single_field(self) -> None:
        """Validate selecting a single field."""
        query = ODataQuery().select("Name")
        result = query.build()
        assert result["$select"] == "Name"

    def test_select_multiple_fields(self) -> None:
        """Validate selecting multiple fields."""
        query = ODataQuery().select("Name", "Age", "Balance")
        result = query.build()
        assert result["$select"] == "Name,Age,Balance"

    def test_select_returns_self_for_chaining(self) -> None:
        """Validate that select() returns self for method chaining."""
        query = ODataQuery()
        result = query.select("Name")
        assert result is query

    def test_select_can_be_chained_multiple_times(self) -> None:
        """Validate that select() can be called multiple times."""
        query = ODataQuery().select("Name").select("Age").select("Balance")
        result = query.build()
        assert result["$select"] == "Name,Age,Balance"

    @pytest.mark.parametrize(
        "field_name",
        ["Name", "CustomerName", "Posting_Date", "Address2", "camelCase", "UPPERCASE"],
        ids=["simple", "compound", "underscore", "with_number", "camelCase", "uppercase"],
    )
    def test_select_accepts_valid_field_names(self, field_name: str) -> None:
        """Validate that select() accepts various valid field name formats.

        Args:
            field_name: The field name to select.
        """
        query = ODataQuery().select(field_name)
        result = query.build()
        assert result["$select"] == field_name

    @pytest.mark.parametrize(
        "invalid_field",
        ["", "   ", "\t", "\n"],
        ids=["empty", "spaces", "tab", "newline"],
    )
    def test_select_rejects_empty_field_names(self, invalid_field: str) -> None:
        """Validate that select() rejects empty or whitespace-only field names.

        Args:
            invalid_field: The invalid field name to test.
        """
        with pytest.raises(QueryValidationError, match="Select field cannot be empty"):
            ODataQuery().select(invalid_field)

    def test_select_rejects_empty_string_among_valid_fields(self) -> None:
        """Validate that an empty string among valid fields raises error."""
        with pytest.raises(QueryValidationError, match="Select field cannot be empty"):
            ODataQuery().select("Name", "", "Balance")


# =============================================================================
# Filter Method Tests
# =============================================================================


class TestFilterMethod:
    """Test suite for ODataQuery.filter() method.

    filter() adds typed filter expressions to the query.
    Multiple filters are AND'd together.
    """

    def test_filter_with_comparison(self) -> None:
        """Validate filtering with a Comparison expression."""
        query = ODataQuery().filter(Comparison("Status", "eq", "Active"))
        result = query.build()
        assert result["$filter"] == "Status eq 'Active'"

    def test_filter_with_field_comparison(self) -> None:
        """Validate filtering using F factory."""
        query = ODataQuery().filter(F.Status == "Active")
        result = query.build()
        assert result["$filter"] == "Status eq 'Active'"

    def test_filter_returns_self_for_chaining(self) -> None:
        """Validate that filter() returns self for method chaining."""
        query = ODataQuery()
        result = query.filter(F.Status == "Active")
        assert result is query

    def test_filter_multiple_conditions_are_anded(self) -> None:
        """Validate that multiple filter() calls are AND'd together."""
        query = ODataQuery().filter(F.Status == "Active").filter(F.Balance > 1000)
        result = query.build()
        assert result["$filter"] == "Status eq 'Active' and Balance gt 1000"

    def test_filter_with_three_conditions(self) -> None:
        """Validate that three filter() calls are properly AND'd."""
        query = ODataQuery().filter(F.Status == "Active").filter(F.Balance > 1000).filter(F.Type == "Customer")
        result = query.build()
        assert result["$filter"] == "Status eq 'Active' and Balance gt 1000 and Type eq 'Customer'"

    def test_filter_with_inlist(self) -> None:
        """Validate filtering with an InList expression."""
        query = ODataQuery().filter(InList("Status", ("Active", "Pending")))
        result = query.build()
        assert result["$filter"] == "(Status eq 'Active' or Status eq 'Pending')"

    def test_filter_with_f_is_in(self) -> None:
        """Validate filtering using F.field.is_in()."""
        query = ODataQuery().filter(F.Status.is_in(["Active", "Pending"]))
        result = query.build()
        assert result["$filter"] == "(Status eq 'Active' or Status eq 'Pending')"

    def test_filter_with_and_expression(self) -> None:
        """Validate filtering with an And expression."""
        query = ODataQuery().filter((F.Status == "Active") & (F.Type == "Sale"))
        result = query.build()
        assert result["$filter"] == "(Status eq 'Active' and Type eq 'Sale')"

    def test_filter_with_or_expression(self) -> None:
        """Validate filtering with an Or expression."""
        query = ODataQuery().filter((F.Status == "Active") | (F.Status == "Pending"))
        result = query.build()
        assert result["$filter"] == "(Status eq 'Active' or Status eq 'Pending')"

    def test_filter_with_raw(self) -> None:
        """Validate filtering with a Raw expression."""
        query = ODataQuery().filter(Raw("contains(Name, 'Corp')"))
        result = query.build()
        assert result["$filter"] == "contains(Name, 'Corp')"

    def test_filter_rejects_non_expression_type(self) -> None:
        """Validate that filter() rejects non-FilterExpression types."""
        with pytest.raises(
            TypeError,
            match=r"filter\(\) requires FilterExpr, got str. Use filter_raw\(\) for raw strings.",
        ):
            ODataQuery().filter("Status eq 'Active'")

    def test_filter_rejects_integer(self) -> None:
        """Validate that filter() rejects integer type."""
        with pytest.raises(
            TypeError,
            match=r"filter\(\) requires FilterExpr, got int",
        ):
            ODataQuery().filter(123)

    def test_filter_rejects_dict(self) -> None:
        """Validate that filter() rejects dict type."""
        with pytest.raises(
            TypeError,
            match=r"filter\(\) requires FilterExpr, got dict",
        ):
            ODataQuery().filter({"Status": "Active"})


# =============================================================================
# Filter Raw Method Tests
# =============================================================================


class TestFilterRawMethod:
    """Test suite for ODataQuery.filter_raw() method.

    filter_raw() adds raw OData filter strings (escape hatch).
    """

    def test_filter_raw_with_contains(self) -> None:
        """Validate filter_raw with contains function."""
        query = ODataQuery().filter_raw("contains(Name, 'Corp')")
        result = query.build()
        assert result["$filter"] == "contains(Name, 'Corp')"

    def test_filter_raw_with_startswith(self) -> None:
        """Validate filter_raw with startswith function."""
        query = ODataQuery().filter_raw("startswith(Email, 'admin')")
        result = query.build()
        assert result["$filter"] == "startswith(Email, 'admin')"

    def test_filter_raw_returns_self_for_chaining(self) -> None:
        """Validate that filter_raw() returns self for method chaining."""
        query = ODataQuery()
        result = query.filter_raw("contains(Name, 'Corp')")
        assert result is query

    def test_filter_raw_multiple_conditions_are_anded(self) -> None:
        """Validate that multiple filter_raw() calls are AND'd together."""
        query = ODataQuery().filter_raw("contains(Name, 'Corp')").filter_raw("length(Name) gt 5")
        result = query.build()
        assert result["$filter"] == "contains(Name, 'Corp') and length(Name) gt 5"

    def test_filter_raw_combined_with_filter(self) -> None:
        """Validate combining filter_raw() with filter()."""
        query = ODataQuery().filter(F.Status == "Active").filter_raw("contains(Name, 'Corp')")
        result = query.build()
        assert result["$filter"] == "Status eq 'Active' and contains(Name, 'Corp')"

    def test_filter_raw_with_complex_expression(self) -> None:
        """Validate filter_raw with complex OData expression."""
        raw_expr = "year(CreatedDate) eq 2024 and month(CreatedDate) ge 6"
        query = ODataQuery().filter_raw(raw_expr)
        result = query.build()
        assert result["$filter"] == raw_expr


# =============================================================================
# Expand Method Tests
# =============================================================================


class TestExpandMethod:
    """Test suite for ODataQuery.expand() method.

    expand() specifies related entities to include in the response.
    """

    def test_expand_single_relation(self) -> None:
        """Validate expanding a single relation."""
        query = ODataQuery().expand("Customer")
        result = query.build()
        assert result["$expand"] == "Customer"

    def test_expand_multiple_relations(self) -> None:
        """Validate expanding multiple relations."""
        query = ODataQuery().expand("Customer", "SalesLines", "Items")
        result = query.build()
        assert result["$expand"] == "Customer,SalesLines,Items"

    def test_expand_returns_self_for_chaining(self) -> None:
        """Validate that expand() returns self for method chaining."""
        query = ODataQuery()
        result = query.expand("Customer")
        assert result is query

    def test_expand_can_be_chained_multiple_times(self) -> None:
        """Validate that expand() can be called multiple times."""
        query = ODataQuery().expand("Customer").expand("SalesLines").expand("Items")
        result = query.build()
        assert result["$expand"] == "Customer,SalesLines,Items"

    @pytest.mark.parametrize(
        "invalid_relation",
        ["", "   ", "\t", "\n"],
        ids=["empty", "spaces", "tab", "newline"],
    )
    def test_expand_rejects_empty_relation_names(self, invalid_relation: str) -> None:
        """Validate that expand() rejects empty or whitespace-only relation names.

        Args:
            invalid_relation: The invalid relation name to test.
        """
        with pytest.raises(QueryValidationError, match="Expand relation cannot be empty"):
            ODataQuery().expand(invalid_relation)

    def test_expand_rejects_empty_string_among_valid_relations(self) -> None:
        """Validate that an empty string among valid relations raises error."""
        with pytest.raises(QueryValidationError, match="Expand relation cannot be empty"):
            ODataQuery().expand("Customer", "", "Items")


# =============================================================================
# Order By Method Tests
# =============================================================================


class TestOrderByMethod:
    """Test suite for ODataQuery.order_by() method.

    order_by() specifies the sort order of results.
    """

    def test_order_by_single_field(self) -> None:
        """Validate ordering by a single field."""
        query = ODataQuery().order_by("Name")
        result = query.build()
        assert result["$orderby"] == "Name"

    def test_order_by_with_asc(self) -> None:
        """Validate ordering with explicit ascending direction."""
        query = ODataQuery().order_by("Name asc")
        result = query.build()
        assert result["$orderby"] == "Name asc"

    def test_order_by_with_desc(self) -> None:
        """Validate ordering with descending direction."""
        query = ODataQuery().order_by("Name desc")
        result = query.build()
        assert result["$orderby"] == "Name desc"

    def test_order_by_multiple_fields(self) -> None:
        """Validate ordering by multiple fields."""
        query = ODataQuery().order_by("Name asc", "Balance desc")
        result = query.build()
        assert result["$orderby"] == "Name asc,Balance desc"

    def test_order_by_returns_self_for_chaining(self) -> None:
        """Validate that order_by() returns self for method chaining."""
        query = ODataQuery()
        result = query.order_by("Name")
        assert result is query

    def test_order_by_can_be_chained_multiple_times(self) -> None:
        """Validate that order_by() can be called multiple times."""
        query = ODataQuery().order_by("Name asc").order_by("Balance desc")
        result = query.build()
        assert result["$orderby"] == "Name asc,Balance desc"

    @pytest.mark.parametrize(
        "invalid_field",
        ["", "   ", "\t", "\n"],
        ids=["empty", "spaces", "tab", "newline"],
    )
    def test_order_by_rejects_empty_field_names(self, invalid_field: str) -> None:
        """Validate that order_by() rejects empty or whitespace-only field names.

        Args:
            invalid_field: The invalid field specification to test.
        """
        with pytest.raises(QueryValidationError, match="Order by field cannot be empty"):
            ODataQuery().order_by(invalid_field)

    def test_order_by_rejects_empty_string_among_valid_fields(self) -> None:
        """Validate that an empty string among valid fields raises error."""
        with pytest.raises(QueryValidationError, match="Order by field cannot be empty"):
            ODataQuery().order_by("Name asc", "", "Balance desc")


# =============================================================================
# Top Method Tests
# =============================================================================


class TestTopMethod:
    """Test suite for ODataQuery.top() method.

    top() limits the number of results returned.
    """

    def test_top_with_integer(self) -> None:
        """Validate setting a top limit."""
        query = ODataQuery().top(100)
        result = query.build()
        assert result["$top"] == "100"

    def test_top_with_zero(self) -> None:
        """Validate setting top to zero."""
        query = ODataQuery().top(0)
        result = query.build()
        assert result["$top"] == "0"

    def test_top_returns_self_for_chaining(self) -> None:
        """Validate that top() returns self for method chaining."""
        query = ODataQuery()
        result = query.top(100)
        assert result is query

    def test_top_overwrites_previous_value(self) -> None:
        """Validate that calling top() again overwrites the previous value."""
        query = ODataQuery().top(100).top(50)
        result = query.build()
        assert result["$top"] == "50"

    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (1, "1"),
            (10, "10"),
            (100, "100"),
            (1000, "1000"),
            (10000, "10000"),
        ],
        ids=["1", "10", "100", "1000", "10000"],
    )
    def test_top_accepts_various_integers(self, count: int, expected: str) -> None:
        """Validate that top() accepts various integer values.

        Args:
            count: The top count value.
            expected: The expected string representation.
        """
        query = ODataQuery().top(count)
        result = query.build()
        assert result["$top"] == expected

    def test_top_rejects_negative_integer(self) -> None:
        """Validate that top() rejects negative integers."""
        with pytest.raises(
            QueryValidationError,
            match=r"top\(\) requires non-negative integer, got -1",
        ):
            ODataQuery().top(-1)

    def test_top_rejects_string(self) -> None:
        """Validate that top() rejects string values."""
        with pytest.raises(
            QueryValidationError,
            match=r"top\(\) requires non-negative integer, got '100'",
        ):
            ODataQuery().top("100")

    def test_top_rejects_float(self) -> None:
        """Validate that top() rejects float values."""
        with pytest.raises(
            QueryValidationError,
            match=r"top\(\) requires non-negative integer, got 10\.5",
        ):
            ODataQuery().top(10.5)

    def test_top_rejects_none(self) -> None:
        """Validate that top() rejects None."""
        with pytest.raises(
            QueryValidationError,
            match=r"top\(\) requires non-negative integer, got None",
        ):
            ODataQuery().top(None)


# =============================================================================
# Skip Method Tests
# =============================================================================


class TestSkipMethod:
    """Test suite for ODataQuery.skip() method.

    skip() is used for pagination to skip a number of results.
    """

    def test_skip_with_integer(self) -> None:
        """Validate setting a skip count."""
        query = ODataQuery().skip(50)
        result = query.build()
        assert result["$skip"] == "50"

    def test_skip_with_zero(self) -> None:
        """Validate setting skip to zero."""
        query = ODataQuery().skip(0)
        result = query.build()
        assert result["$skip"] == "0"

    def test_skip_returns_self_for_chaining(self) -> None:
        """Validate that skip() returns self for method chaining."""
        query = ODataQuery()
        result = query.skip(50)
        assert result is query

    def test_skip_overwrites_previous_value(self) -> None:
        """Validate that calling skip() again overwrites the previous value."""
        query = ODataQuery().skip(50).skip(100)
        result = query.build()
        assert result["$skip"] == "100"

    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (0, "0"),
            (50, "50"),
            (100, "100"),
            (500, "500"),
        ],
        ids=["0", "50", "100", "500"],
    )
    def test_skip_accepts_various_integers(self, count: int, expected: str) -> None:
        """Validate that skip() accepts various integer values.

        Args:
            count: The skip count value.
            expected: The expected string representation.
        """
        query = ODataQuery().skip(count)
        result = query.build()
        assert result["$skip"] == expected

    def test_skip_rejects_negative_integer(self) -> None:
        """Validate that skip() rejects negative integers."""
        with pytest.raises(
            QueryValidationError,
            match=r"skip\(\) requires non-negative integer, got -1",
        ):
            ODataQuery().skip(-1)

    def test_skip_rejects_string(self) -> None:
        """Validate that skip() rejects string values."""
        with pytest.raises(
            QueryValidationError,
            match=r"skip\(\) requires non-negative integer, got '50'",
        ):
            ODataQuery().skip("50")

    def test_skip_rejects_float(self) -> None:
        """Validate that skip() rejects float values."""
        with pytest.raises(
            QueryValidationError,
            match=r"skip\(\) requires non-negative integer, got 5\.5",
        ):
            ODataQuery().skip(5.5)


# =============================================================================
# Count Method Tests
# =============================================================================


class TestCountMethod:
    """Test suite for ODataQuery.count() method.

    count() includes the total count of matching entities in the response.
    """

    def test_count_with_default(self) -> None:
        """Validate that count() with no argument enables counting."""
        query = ODataQuery().count()
        result = query.build()
        assert result["$count"] == "true"

    def test_count_with_true(self) -> None:
        """Validate that count(True) enables counting."""
        query = ODataQuery().count(True)
        result = query.build()
        assert result["$count"] == "true"

    def test_count_with_false(self) -> None:
        """Validate that count(False) disables counting (no $count in output)."""
        query = ODataQuery().count(False)
        result = query.build()
        assert "$count" not in result

    def test_count_returns_self_for_chaining(self) -> None:
        """Validate that count() returns self for method chaining."""
        query = ODataQuery()
        result = query.count()
        assert result is query

    def test_count_can_be_toggled(self) -> None:
        """Validate that count can be enabled and then disabled."""
        query = ODataQuery().count(True).count(False)
        result = query.build()
        assert "$count" not in result

    def test_count_disabled_does_not_appear_in_output(self) -> None:
        """Validate that explicitly disabled count is not in build output."""
        query = ODataQuery().count(False)
        result = query.build()
        assert result == {}


# =============================================================================
# Build Method Tests
# =============================================================================


class TestBuildMethod:
    """Test suite for ODataQuery.build() method.

    build() generates the final dictionary of OData query parameters.
    """

    def test_build_empty_query_returns_empty_dict(self) -> None:
        """Validate that building an empty query returns empty dict."""
        query = ODataQuery()
        assert query.build() == {}

    def test_build_returns_dict(self) -> None:
        """Validate that build() returns a dictionary."""
        query = ODataQuery().select("Name")
        result = query.build()
        assert isinstance(result, dict)

    def test_build_only_includes_set_parameters(self) -> None:
        """Validate that build() only includes parameters that were set."""
        query = ODataQuery().select("Name").top(10)
        result = query.build()
        assert set(result.keys()) == {"$select", "$top"}

    def test_build_does_not_mutate_query(self) -> None:
        """Validate that build() doesn't mutate the query object."""
        query = ODataQuery().select("Name").filter(F.Status == "Active")
        result1 = query.build()
        result2 = query.build()
        assert result1 == result2

    def test_build_is_idempotent(self) -> None:
        """Validate that calling build() multiple times returns same result."""
        query = ODataQuery().select("Name", "Age").filter(F.Status == "Active").top(100)
        result1 = query.build()
        result2 = query.build()
        result3 = query.build()
        assert result1 == result2 == result3


# =============================================================================
# Method Chaining Tests
# =============================================================================


class TestMethodChaining:
    """Test suite for fluent method chaining with ODataQuery."""

    def test_full_chain_returns_correct_dict(self) -> None:
        """Validate a complete method chain returns all parameters."""
        query = (
            ODataQuery()
            .select("No", "Name", "Balance")
            .filter(F.Status == "Active")
            .expand("Customer")
            .order_by("Name asc")
            .top(100)
            .skip(50)
            .count()
        )
        result = query.build()

        assert result["$select"] == "No,Name,Balance"
        assert result["$filter"] == "Status eq 'Active'"
        assert result["$expand"] == "Customer"
        assert result["$orderby"] == "Name asc"
        assert result["$top"] == "100"
        assert result["$skip"] == "50"
        assert result["$count"] == "true"

    def test_chain_order_does_not_affect_result(self) -> None:
        """Validate that method order doesn't affect the final result."""
        query1 = ODataQuery().select("Name").filter(F.Status == "Active").top(10)
        query2 = ODataQuery().top(10).filter(F.Status == "Active").select("Name")
        query3 = ODataQuery().filter(F.Status == "Active").select("Name").top(10)

        result1 = query1.build()
        result2 = query2.build()
        result3 = query3.build()

        assert result1 == result2 == result3

    def test_all_methods_return_self(self) -> None:
        """Validate that all methods return self for chaining."""
        query = ODataQuery()

        assert query.select("Name") is query
        assert query.filter(F.Status == "Active") is query
        assert query.filter_raw("contains(Name, 'Corp')") is query
        assert query.expand("Customer") is query
        assert query.order_by("Name") is query
        assert query.top(10) is query
        assert query.skip(5) is query
        assert query.count() is query


# =============================================================================
# Complex Query Tests (Real-World Usage Patterns)
# =============================================================================


class TestComplexQueries:
    """Test suite for complex, real-world query patterns."""

    def test_pagination_query(self) -> None:
        """Validate a pagination query with top, skip, and count."""
        page_size = 20
        page_number = 3  # 0-indexed

        query = (
            ODataQuery()
            .select("No", "Name", "Balance")
            .order_by("Name asc")
            .top(page_size)
            .skip(page_number * page_size)
            .count()
        )
        result = query.build()

        assert result["$select"] == "No,Name,Balance"
        assert result["$orderby"] == "Name asc"
        assert result["$top"] == "20"
        assert result["$skip"] == "60"
        assert result["$count"] == "true"

    def test_filtered_search_query(self) -> None:
        """Validate a filtered search query with multiple conditions."""
        query = (
            ODataQuery()
            .select("No", "Name", "Type", "Balance")
            .filter(F.Type == "Customer")
            .filter(F.Balance > 10000)
            .filter(F.Status == "Active")
            .order_by("Balance desc")
            .top(50)
        )
        result = query.build()

        assert result["$select"] == "No,Name,Type,Balance"
        assert result["$filter"] == "Type eq 'Customer' and Balance gt 10000 and Status eq 'Active'"
        assert result["$orderby"] == "Balance desc"
        assert result["$top"] == "50"

    def test_date_range_filter_query(self) -> None:
        """Validate a query with date range filtering."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)

        query = (
            ODataQuery()
            .select("No", "PostingDate", "Amount")
            .filter(F.PostingDate >= start_date)
            .filter(F.PostingDate <= end_date)
            .order_by("PostingDate desc")
        )
        result = query.build()

        assert result["$select"] == "No,PostingDate,Amount"
        assert result["$filter"] == "PostingDate ge 2024-01-01 and PostingDate le 2024-12-31"
        assert result["$orderby"] == "PostingDate desc"

    def test_datetime_filter_query(self) -> None:
        """Validate a query with datetime filtering."""
        timestamp = datetime(2024, 6, 15, 14, 30, 0)

        query = ODataQuery().filter(F.CreatedAt >= timestamp)
        result = query.build()

        assert result["$filter"] == "CreatedAt ge 2024-06-15T14:30:00Z"

    def test_in_list_with_other_conditions(self) -> None:
        """Validate a query with IN-list combined with other filters."""
        query = (
            ODataQuery()
            .select("No", "Name", "Type")
            .filter(F.Type.is_in(["Sale", "Purchase", "Return"]))
            .filter(F.Status == "Active")
            .order_by("Name")
        )
        result = query.build()

        assert result["$select"] == "No,Name,Type"
        assert result["$filter"] == "(Type eq 'Sale' or Type eq 'Purchase' or Type eq 'Return') and Status eq 'Active'"

    def test_or_condition_query(self) -> None:
        """Validate a query with OR conditions using expression operators."""
        query = (
            ODataQuery()
            .select("No", "Name", "Status")
            .filter((F.Status == "Active") | (F.Status == "Pending"))
            .top(100)
        )
        result = query.build()

        assert result["$filter"] == "(Status eq 'Active' or Status eq 'Pending')"

    def test_complex_boolean_expression(self) -> None:
        """Validate a complex query with nested AND/OR conditions."""
        query = ODataQuery().filter(
            ((F.Type == "Customer") & (F.Balance > 10000)) | ((F.Type == "Vendor") & (F.Balance < -5000))
        )
        result = query.build()

        assert result["$filter"] == (
            "((Type eq 'Customer' and Balance gt 10000) or (Type eq 'Vendor' and Balance lt -5000))"
        )

    def test_mixed_filter_and_filter_raw(self) -> None:
        """Validate mixing typed filters with raw filter expressions."""
        query = (
            ODataQuery()
            .select("No", "Name", "Email")
            .filter(F.Status == "Active")
            .filter_raw("contains(Name, 'Corp')")
            .filter_raw("startswith(Email, 'admin')")
            .top(10)
        )
        result = query.build()

        expected_filter = "Status eq 'Active' and contains(Name, 'Corp') and startswith(Email, 'admin')"
        assert result["$filter"] == expected_filter

    def test_expand_with_filters(self) -> None:
        """Validate expand combined with filters."""
        query = ODataQuery().select("No", "Name").expand("SalesLines", "Customer").filter(F.Status == "Active")
        result = query.build()

        assert result["$select"] == "No,Name"
        assert result["$expand"] == "SalesLines,Customer"
        assert result["$filter"] == "Status eq 'Active'"

    def test_string_with_special_characters(self) -> None:
        """Validate query with string value containing special characters."""
        query = ODataQuery().filter(F.Name == "O'Brien & Co.")
        result = query.build()

        # Single quotes should be escaped by doubling them
        assert result["$filter"] == "Name eq 'O''Brien & Co.'"

    def test_null_comparison(self) -> None:
        """Validate query with null comparison."""
        query = ODataQuery().filter(F.DeletedAt == None)  # noqa: E711
        result = query.build()

        assert result["$filter"] == "DeletedAt eq null"

    def test_boolean_comparison(self) -> None:
        """Validate query with boolean comparisons."""
        query = (
            ODataQuery()
            .filter(F.IsActive == True)  # noqa: E712
            .filter(F.IsDeleted == False)  # noqa: E712
        )
        result = query.build()

        assert result["$filter"] == "IsActive eq true and IsDeleted eq false"


# =============================================================================
# Query Independence Tests
# =============================================================================


class TestQueryIndependence:
    """Test suite to verify that query instances are independent."""

    def test_separate_queries_are_independent(self) -> None:
        """Validate that two query instances don't share state."""
        query1 = ODataQuery().select("Name")
        query2 = ODataQuery().select("Age")

        result1 = query1.build()
        result2 = query2.build()

        assert result1["$select"] == "Name"
        assert result2["$select"] == "Age"

    def test_modifying_one_query_doesnt_affect_another(self) -> None:
        """Validate that modifying one query doesn't affect another."""
        base_select = ["Name"]

        query1 = ODataQuery()
        query1._select = base_select.copy()

        query2 = ODataQuery()
        query2._select = base_select.copy()

        # Modify query1
        query1.select("Age")

        # Check that query2 is unaffected
        assert query1._select == ["Name", "Age"]
        assert query2._select == ["Name"]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_very_long_select_list(self) -> None:
        """Validate query with many selected fields."""
        fields = [f"Field{i}" for i in range(50)]
        query = ODataQuery().select(*fields)
        result = query.build()

        assert result["$select"] == ",".join(fields)

    def test_very_long_filter_chain(self) -> None:
        """Validate query with many filter conditions."""
        query = ODataQuery()
        for i in range(10):
            query.filter(Comparison(f"Field{i}", "eq", i))

        result = query.build()
        parts = result["$filter"].split(" and ")

        assert len(parts) == 10

    def test_large_top_value(self) -> None:
        """Validate query with a large top value."""
        query = ODataQuery().top(1000000)
        result = query.build()

        assert result["$top"] == "1000000"

    def test_large_skip_value(self) -> None:
        """Validate query with a large skip value."""
        query = ODataQuery().skip(1000000)
        result = query.build()

        assert result["$skip"] == "1000000"

    def test_numeric_string_value_in_filter(self) -> None:
        """Validate filter with numeric-looking string value."""
        query = ODataQuery().filter(F.Code == "12345")
        result = query.build()

        # Should be quoted as a string
        assert result["$filter"] == "Code eq '12345'"

    def test_empty_string_value_in_filter(self) -> None:
        """Validate filter with empty string value."""
        query = ODataQuery().filter(F.Name == "")
        result = query.build()

        assert result["$filter"] == "Name eq ''"

    def test_whitespace_string_value_in_filter(self) -> None:
        """Validate filter with whitespace-only string value."""
        query = ODataQuery().filter(F.Name == "   ")
        result = query.build()

        assert result["$filter"] == "Name eq '   '"

    def test_float_comparison_precision(self) -> None:
        """Validate filter with float values preserves precision."""
        query = ODataQuery().filter(F.Amount == 99.99)
        result = query.build()

        assert result["$filter"] == "Amount eq 99.99"

    def test_negative_number_in_filter(self) -> None:
        """Validate filter with negative number."""
        query = ODataQuery().filter(F.Balance < -1000)
        result = query.build()

        assert result["$filter"] == "Balance lt -1000"
