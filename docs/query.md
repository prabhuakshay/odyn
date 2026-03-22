# Query Builder

Odyn provides a type-safe, fluent API for building OData query parameters. Instead of manually constructing query strings, you use `ODataQuery` for method chaining and the `F` singleton for filter expressions.

## Imports

```python
from odyn.query import ODataQuery, F
```

## ODataQuery

`ODataQuery` is a mutable builder. All methods return `self` for chaining. Call `.build()` to produce a `dict[str, str]` of OData query parameters.

### Methods

| Method | OData param | Description |
|--------|-------------|-------------|
| `.select(*fields)` | `$select` | Fields to return |
| `.filter(expr)` | `$filter` | Filter condition (multiple calls are AND'd) |
| `.filter_raw(str)` | `$filter` | Raw OData filter string (escape hatch) |
| `.expand(*relations)` | `$expand` | Related entities to include |
| `.order_by(*fields)` | `$orderby` | Sort order (e.g., `"Name asc"`, `"Balance desc"`) |
| `.top(n)` | `$top` | Limit results |
| `.skip(n)` | `$skip` | Skip first N results |
| `.count()` | `$count` | Include total count in response |
| `.build()` | — | Returns `dict[str, str]` |

### Full Example

```python
query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY", "City")
    .filter(F.Balance_LCY > 1000)
    .filter(F.Blocked == False)
    .expand("SalesLines")
    .order_by("Balance_LCY desc", "Name asc")
    .top(100)
    .skip(50)
    .count()
)

params = query.build()
# {
#     '$select': 'No,Name,Balance_LCY,City',
#     '$filter': "Balance_LCY gt 1000 and Blocked eq false",
#     '$expand': 'SalesLines',
#     '$orderby': 'Balance_LCY desc,Name asc',
#     '$top': '100',
#     '$skip': '50',
#     '$count': 'true',
# }
```

### Multiple Filters

Multiple `.filter()` calls are combined with `and`:

```python
query = (
    ODataQuery()
    .filter(F.Status == "Active")
    .filter(F.Balance_LCY > 0)
    .filter(F.City != "")
)
# $filter: Status eq 'Active' and Balance_LCY gt 0 and City ne ''
```

### Validation

All methods validate their inputs and raise `QueryValidationError` for:

- Empty field names in `.select()`, `.expand()`, `.order_by()`
- Non-`FilterExpression` values in `.filter()` (use `.filter_raw()` for strings)
- Negative integers in `.top()` and `.skip()`

## The F Singleton

`F` is a field factory that creates `Field` objects via attribute access. Fields support Python comparison operators that produce OData filter expressions.

```python
from odyn.query import F

F.Name        # Field("Name")
F.Balance_LCY # Field("Balance_LCY")
F.Status      # Field("Status")
```

Field names are validated against OData identifier rules:
- Must start with a letter or underscore
- Can only contain alphanumeric characters and underscores

### Comparison Operators

| Python | OData | Example |
|--------|-------|---------|
| `==` | `eq` | `F.Status == "Active"` |
| `!=` | `ne` | `F.City != ""` |
| `>` | `gt` | `F.Balance > 1000` |
| `>=` | `ge` | `F.Balance >= 0` |
| `<` | `lt` | `F.Balance < 500` |
| `<=` | `le` | `F.Count <= 10` |

### IN Lists

OData has no native `IN` operator. Odyn generates an OR chain of equality comparisons:

```python
F.Type.is_in(["Sale", "Purchase", "Return"])
# (Type eq 'Sale' or Type eq 'Purchase' or Type eq 'Return')
```

### Supported Value Types

The `ODataValue` type alias defines what values can be used in comparisons:

| Python type | OData format | Example |
|-------------|-------------|---------|
| `str` | `'value'` (single-quoted, `'` escaped to `''`) | `F.Name == "O'Brien"` → `Name eq 'O''Brien'` |
| `int` | `123` | `F.Count == 5` → `Count eq 5` |
| `float` | `1.5` | `F.Rate == 1.5` → `Rate eq 1.5` |
| `bool` | `true` / `false` | `F.Active == True` → `Active eq true` |
| `None` | `null` | `F.Code == None` → `Code eq null` |
| `date` | `2024-01-15` | `F.PostingDate == date(2024, 1, 15)` |
| `datetime` | `2024-01-15T10:30:00Z` | `F.ModifiedAt > datetime(2024, 1, 15, 10, 30)` |

## Expression Types

All expressions implement the `FilterExpression` protocol (must have a `to_odata() -> str` method).

### Comparison

A single field comparison. Created by Field operators.

```python
from odyn.query.expressions import Comparison

expr = Comparison(field="Name", operator="eq", value="John")
expr.to_odata()  # "Name eq 'John'"
```

Attributes: `field: str`, `operator: str`, `value: ODataValue`

Valid operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`

### InList

IN-style filter via OR-chained equalities.

```python
from odyn.query.expressions import InList

expr = InList(field="Status", values=("Active", "Pending"))
expr.to_odata()  # "(Status eq 'Active' or Status eq 'Pending')"
```

Attributes: `field: str`, `values: tuple[ODataValue, ...]`

Requires at least one value.

### Raw

Escape hatch for OData functions and syntax not covered by the typed expression classes.

```python
from odyn.query.expressions import Raw

expr = Raw("contains(Name, 'Corp')")
expr.to_odata()  # "contains(Name, 'Corp')"

# Use via query builder
query = ODataQuery().filter_raw("startswith(Email, 'admin')")
```

Attributes: `expression: str`

Cannot be empty.

### And / Or

Logical combinations of expressions. Typically created using `&` and `|` operators.

```python
# Using operators (recommended)
expr = (F.Status == "Active") & (F.Balance > 0)
expr.to_odata()  # "(Status eq 'Active' and Balance gt 0)"

expr = (F.City == "London") | (F.City == "Berlin")
expr.to_odata()  # "(City eq 'London' or City eq 'Berlin')"
```

Chaining flattens nested expressions:

```python
expr = (F.A == 1) & (F.B == 2) & (F.C == 3)
# And((Comparison(A, eq, 1), Comparison(B, eq, 2), Comparison(C, eq, 3)))
# "(A eq 1 and B eq 2 and C eq 3)"
```

You can mix `&` and `|`:

```python
expr = ((F.City == "London") | (F.City == "Berlin")) & (F.Balance > 1000)
# "((City eq 'London' or City eq 'Berlin') and Balance gt 1000)"
```

### Direct Construction

You can also construct `And` and `Or` directly:

```python
from odyn.query.expressions import And, Or

And((expr_a, expr_b))       # requires tuple of 2+ expressions
Or((expr_a, expr_b, expr_c)) # requires tuple of 2+ expressions
```

## FilterExpression Protocol

Any object with a `to_odata() -> str` method satisfies `FilterExpression`. This means you can create custom expression types:

```python
from odyn.query.expressions import FilterExpression

class SubstringOf:
    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value

    def to_odata(self) -> str:
        return f"substringof('{self.value}', {self.field})"

# Use with ODataQuery.filter()
query = ODataQuery().filter(SubstringOf("Name", "Corp"))
```

The protocol is runtime-checkable (`@runtime_checkable`), so `isinstance(obj, FilterExpression)` works.

## Common Patterns

### Combining with additional filters in get_batch

```python
df = await client.get_batch(
    "customers",
    field="No",
    values=customer_ids,
    additional_filter=(F.Blocked == False),
)
```

### Date range queries

```python
from datetime import date

query = (
    ODataQuery()
    .filter(F.Posting_Date >= date(2024, 1, 1))
    .filter(F.Posting_Date <= date(2024, 12, 31))
)
```

### Null checks

```python
query = ODataQuery().filter(F.Email != None)
# $filter: Email ne null
```

### OData functions via filter_raw

```python
query = (
    ODataQuery()
    .filter_raw("contains(Name, 'Corp')")
    .filter_raw("startswith(Email, 'sales')")
    .filter(F.Balance > 0)
)
# $filter: contains(Name, 'Corp') and startswith(Email, 'sales') and Balance gt 0
```

Raw filters can be freely mixed with typed expressions — they're all AND'd together.
