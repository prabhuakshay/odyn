# Query Builder Guide

Odyn provides a type-safe, fluent API for building OData query strings. This prevents syntax errors and provides IDE auto-completion for query operators.

## The `ODataQuery` Object

The `ODataQuery` class allows you to chain methods to build complex URL parameters like `$select`, `$filter`, `$expand`, and `$orderby`.

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name")
    .filter(F.Status == "Active")
    .order_by("Name asc")
    .top(10)
)
```

## Field Expressions (`F`)

The `F` object is a proxy that makes it easy to reference fields. Accessing any attribute on `F` returns a `Field` object that supports Python's comparison operators.

### Comparisons

| Python Operator | OData Equivalent | Example |
|-----------------|------------------|---------|
| `==`            | `eq`             | `F.Status == "Open"` |
| `!=`            | `ne`             | `F.Type != "Service"` |
| `>`             | `gt`             | `F.Quantity > 0` |
| `>=`            | `ge`             | `F.Amount >= 100` |
| `<`             | `lt`             | `F.Date < date(2024, 1, 1)` |
| `<=`            | `le`             | `F.Balance <= 0` |

### Logical Combinations

You can combine multiple filter expressions using the `&` (AND) and `|` (OR) operators.

```python
# (Status eq 'Active' and Balance gt 1000)
expr = (F.Status == "Active") & (F.Balance > 1000)

# (Type eq 'Sale' or Type eq 'Purchase')
expr = (F.Type == "Sale") | (F.Type == "Purchase")
```

### IN Expressions

OData does not have a native `IN` operator. Odyn provides an `is_in()` method on fields that automatically expands to a chain of `OR` equalities.

```python
# (Status eq 'Draft' or Status eq 'Pending')
expr = F.Status.is_in(["Draft", "Pending"])
```

## Raw Expressions

If you need to use OData functions (like `contains`, `startswith`) or complex expressions not yet supported by the fluent API, you can use `filter_raw()`.

```python
query = ODataQuery().filter_raw("contains(Name, 'Corp')")
```

## Expansion

The `expand()` method allows you to include related entities in the response.

```python
# Fetch customers including their sales orders
query = ODataQuery().expand("SalesOrders")
```

Note: Business Central Web Services have strict limits on nested expansions and the number of fields returned in expanded entities.
