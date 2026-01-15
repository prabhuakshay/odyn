# Odyn - Complete Reference for LLM Context

This document provides complete documentation for Odyn, a Python client for Microsoft Dynamics 365 Business Central on-premises OData Web Services. Upload this file to an LLM to enable expert assistance with Odyn.

---

## Overview

Odyn is an async-first Python library for fetching data from Business Central OData V4 endpoints. It returns data as Polars DataFrames and includes automatic pagination, caching, retry logic, rate limiting, and a fluent query builder.

**Key Features:**
- Async/await with httpx (sync wrapper also available)
- Polars DataFrames for efficient data handling
- Automatic pagination following `@odata.nextLink`
- Parquet-based caching with TTL
- Exponential backoff retries
- Rate limiting (token bucket algorithm)
- Fluent OData query builder
- Progress callbacks and request/response hooks

---

## Installation

```bash
pip install odyn
# or
uv add odyn
```

**Dependencies:** httpx, polars, aiolimiter

---

## Quick Start

### Async Usage (Recommended)

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        company="CRONUS",
        auth=BasicAuth("DOMAIN\\user", "password"),
    ) as client:
        # Fetch all customers
        customers = await client.get("customers")
        print(customers)

asyncio.run(main())
```

### Sync Usage (For Scripts/Notebooks)

```python
from odyn import BCWebServiceClientSync, BasicAuth

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    company="CRONUS",
    auth=BasicAuth("DOMAIN\\user", "password"),
) as client:
    customers = client.get("customers")
    print(customers)
```

---

## Authentication

Use `BasicAuth` for on-premises Business Central:

```python
from odyn import BasicAuth

# Without domain
auth = BasicAuth("username", "password")

# With domain (use double backslash in Python strings)
auth = BasicAuth("DOMAIN\\username", "password")
```

**Note:** Some BC configurations require the Web Service Access Key from the User card instead of the Windows password.

---

## Client Configuration

### BCWebServiceClient.create() Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server` | `str` | required | BC server URL (e.g., `https://bc-server:7048`) |
| `instance` | `str` | required | BC instance name (e.g., `BC210`, `BC230`) |
| `auth` | `BasicAuth` | required | Authentication credentials |
| `company` | `str` | `None` | Company name to scope all requests |
| `timeout` | `float` | `30.0` | Request timeout in seconds |
| `max_pages` | `int` | `100` | Max pages for auto-pagination |
| `verify_ssl` | `bool` | `True` | Verify SSL certificates (set `False` for self-signed) |
| `cache_dir` | `str/Path` | `None` | Directory for Parquet cache files |
| `cache_ttl` | `int` | `None` | Cache TTL in seconds |
| `max_retries` | `int` | `3` | Max retry attempts for transient errors |
| `retry_backoff` | `float` | `1.0` | Base delay for exponential backoff |
| `max_connections` | `int` | `4` | Max concurrent connections |
| `requests_per_minute` | `float` | `550.0` | Rate limit (set `None` to disable) |
| `max_burst` | `int` | `None` | Burst size (defaults to `max_connections`) |
| `on_request` | `callable` | `None` | Hook called before each request |
| `on_response` | `callable` | `None` | Hook called after each response |

### Example with Full Configuration

```python
client = BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("DOMAIN\\user", "password"),
    company="CRONUS International Ltd.",
    verify_ssl=False,  # For self-signed certs
    cache_dir="~/.cache/odyn",
    cache_ttl=3600,  # 1 hour
    max_retries=5,
    requests_per_minute=300.0,
)
```

---

## Fetching Data

### get() - Fetch with Auto-Pagination

```python
# Simple fetch
df = await client.get("customers")

# With query
from odyn.query import ODataQuery, F
query = ODataQuery().filter(F.Balance > 1000).top(50)
df = await client.get("customers", query=query)

# Without pagination (single page only)
df = await client.get("customers", paginate=False)

# Skip cache
df = await client.get("customers", use_cache=False)
```

**Returns:** `polars.DataFrame`

### get_stream() - Stream Pages

For large datasets, stream one page at a time:

```python
async for page_df in client.get_stream("largeDataset"):
    process(page_df)
```

### get_by_key() - Fetch Single Record by Primary Key

```python
customer = await client.get_by_key("customers", "C001")
# Returns: {"No": "C001", "Name": "...", ...}

# With field selection
customer = await client.get_by_key("customers", "C001", select=["No", "Name"])
```

**Returns:** `dict[str, Any]`

### get_by_id() - Fetch by SystemId (GUID)

```python
customer = await client.get_by_id("customers", "12345678-1234-1234-1234-123456789012")
```

**Returns:** `dict[str, Any]`

### count() - Get Record Count

```python
total = await client.count("customers")

# With filter
query = ODataQuery().filter(F.Status == "Active")
active_count = await client.count("customers", query=query)
```

**Returns:** `int`

### get_first() - Get First Matching Record

```python
customer = await client.get_first("customers", query=ODataQuery().filter(F.Name == "John"))
# Returns dict or None
```

### exists() - Check if Record Exists

```python
if await client.exists("customers", "C001"):
    print("Customer exists")
```

**Returns:** `bool`

### get_all() - Optimized Full Fetch

```python
all_customers = await client.get_all("customers", batch_size=1000)
```

### get_batch() - Fetch by List of Values

Efficiently fetch records matching a large list of IDs (auto-chunks to avoid URL length limits):

```python
customer_ids = ["C001", "C002", "C003", ..., "C500"]

customers = await client.get_batch(
    endpoint="customers",
    field="No",
    values=customer_ids,
    batch_size=50,  # Values per request
    select=["No", "Name", "Balance"],
    fail_fast=False,  # Continue on individual batch failures
)
```

With additional filter:

```python
from odyn.query import F

active_customers = await client.get_batch(
    "customers",
    "No",
    customer_ids,
    additional_filter=(F.Blocked == False),
)
```

### get_endpoints() - List Available Endpoints

```python
endpoints = await client.get_endpoints()
# Returns: ["customers", "vendors", "items", ...]
```

---

## Delta Sync (Incremental Updates)

### get_since() - Records Modified After Timestamp

```python
from datetime import datetime, timedelta, timezone

# Get records modified in the last hour
since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
updated = await client.get_since("customers", since)

# With additional query
query = ODataQuery().select("No", "Name", "SystemModifiedAt")
updated = await client.get_since("customers", since, query=query)
```

**Note:** `use_cache=False` by default for fresh data.

### get_before() - Records Modified Before Timestamp

```python
# Get records not modified in 30 days
before = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
stale = await client.get_before("customers", before)
```

**Note:** `use_cache=True` by default for historical data.

---

## Query Building

### ODataQuery - Fluent Builder

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance", "City")
    .filter(F.Balance > 1000)
    .filter(F.City == "Seattle")  # Multiple filters are ANDed
    .expand("SalesLines")
    .order_by("Balance desc", "Name asc")
    .top(100)
    .skip(50)
)

df = await client.get("customers", query=query)
```

### F Proxy - Field Expressions

```python
from odyn.query import F

# Comparison operators
F.Balance > 1000
F.Balance >= 1000
F.Balance < 500
F.Balance <= 500
F.Status == "Active"
F.Status != "Blocked"

# Combine with & (AND) and | (OR)
(F.Balance > 1000) & (F.Status == "Active")
(F.City == "Seattle") | (F.City == "Portland")

# IN operator
F.No.is_in(["C001", "C002", "C003"])
```

### Raw Filters

For complex OData expressions not supported by the builder:

```python
query = ODataQuery().filter_raw("contains(Name, 'Corp')")
```

### Complete Query Example

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY", "City")
    .filter((F.Balance_LCY > 10000) & (F.Blocked == False))
    .order_by("Balance_LCY desc")
    .top(50)
)

top_customers = await client.get("customers", query=query)
```

---

## Caching

Enable caching by providing `cache_dir`:

```python
client = BCWebServiceClient.create(
    ...,
    cache_dir="~/.cache/odyn",
    cache_ttl=3600,  # 1 hour
)

# First call fetches from API and caches
df = await client.get("customers")

# Second call returns cached data
df = await client.get("customers")

# Force refresh
df = await client.get("customers", use_cache=False)
```

### Cache Management

```python
# Get cache statistics
stats = client.cache_stats
# {"hits": 10, "misses": 2, "disk_bytes": 1048576}

# Get cache size
size = client.cache_size

# Remove expired entries
removed = client.cleanup_cache()

# Clear all cache
removed = client.clear_cache()
```

---

## Progress Callbacks

### Pagination Progress

```python
def on_progress(*, page, records_on_page, total_records, is_final):
    print(f"Page {page}: {records_on_page} records (total: {total_records})")
    if is_final:
        print("Done!")

df = await client.get("customers", on_progress=on_progress)
```

### Batch Progress

```python
def on_batch_progress(*, batch, total_batches, successful, failed, is_final):
    pct = batch / total_batches * 100
    print(f"Batch {batch}/{total_batches} ({pct:.0f}%) - {successful} ok, {failed} failed")

df = await client.get_batch(
    "customers", "No", large_id_list,
    on_progress=on_batch_progress
)
```

---

## Request/Response Hooks

For logging, metrics, or debugging:

```python
def log_request(*, method, url, params):
    print(f">> {method} {url}")

def log_response(*, method, url, status_code, duration_ms):
    print(f"<< {status_code} in {duration_ms:.0f}ms")

client = BCWebServiceClient.create(
    ...,
    on_request=log_request,
    on_response=log_response,
)
```

---

## Error Handling

### Exception Hierarchy

```
OdynError (base)
├── OdynConnectionError
│   ├── OdynTimeoutError
│   └── OdynSSLError
├── WebServiceError
│   ├── AuthenticationError (401)
│   ├── ForbiddenError (403)
│   ├── NotFoundError (404)
│   ├── ValidationError (400)
│   ├── RateLimitError (429)
│   └── ServerError (5xx)
├── RetryExhaustedError
└── QueryValidationError
```

### Example Error Handling

```python
from odyn import BCWebServiceClient, BasicAuth
from odyn.exceptions import NotFoundError, AuthenticationError, RetryExhaustedError

try:
    customer = await client.get_by_key("customers", "INVALID")
except NotFoundError:
    print("Customer not found")
except AuthenticationError:
    print("Invalid credentials")
except RetryExhaustedError as e:
    print(f"Request failed after {e.attempts} attempts: {e.last_exception}")
```

### WebServiceError Attributes

```python
try:
    await client.get("invalid_endpoint")
except WebServiceError as e:
    print(e.message)        # Error message
    print(e.status_code)    # HTTP status code
    print(e.url)            # Request URL
    print(e.response_body)  # Raw response body
    print(e.odata_error)    # Parsed OData error object
```

---

## Sync Client Reference

`BCWebServiceClientSync` provides identical methods without `await`:

```python
from odyn import BCWebServiceClientSync, BasicAuth

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
) as client:
    # All methods are blocking (no await)
    df = client.get("customers")
    customer = client.get_by_key("customers", "C001")
    count = client.count("customers")
    exists = client.exists("customers", "C001")
    updated = client.get_since("customers", "2024-01-01T00:00:00Z")
    batched = client.get_batch("customers", "No", ["C001", "C002"])
```

---

## Common Patterns

### Incremental Data Pipeline

```python
from datetime import datetime, timezone

async def sync_customers(client, last_sync: datetime):
    # Fetch only records modified since last sync
    timestamp = last_sync.isoformat()
    updated = await client.get_since("customers", timestamp)

    # Process updates
    for row in updated.iter_rows(named=True):
        process_customer(row)

    return datetime.now(timezone.utc)
```

### Parallel Batch Processing

```python
async def fetch_all_related_data(client, customer_ids):
    # Fetch customers and their related data in parallel
    customers, invoices = await asyncio.gather(
        client.get_batch("customers", "No", customer_ids),
        client.get_batch("salesInvoices", "Sell_to_Customer_No", customer_ids),
    )
    return customers, invoices
```

### With Polars Operations

```python
import polars as pl

# Fetch and transform
customers = await client.get("customers")
high_value = (
    customers
    .filter(pl.col("Balance_LCY") > 10000)
    .sort("Balance_LCY", descending=True)
    .select(["No", "Name", "Balance_LCY"])
)
```

### Using with pandas

```python
# Convert Polars DataFrame to pandas
customers = await client.get("customers")
customers_pd = customers.to_pandas()
```

---

## Troubleshooting

### 401 Unauthorized
- Ensure domain prefix is included: `BasicAuth("DOMAIN\\user", "pass")`
- Try using Web Service Access Key instead of Windows password

### 404 Not Found
- Verify endpoint name matches exactly (case-sensitive) the "Service Name" in BC Web Services page
- Ensure the service is Published in BC

### SSL Errors
- Set `verify_ssl=False` for self-signed certificates (internal environments only)

### 429 Rate Limit
- Reduce `requests_per_minute` (e.g., to `300.0`)
- Reduce `max_connections` (e.g., to `2`)

### URL Too Long (414)
- Use `client.get_batch()` instead of large `is_in()` filters

---

## API Quick Reference

### Client Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get(endpoint, ...)` | `DataFrame` | Fetch with auto-pagination |
| `get_stream(endpoint, ...)` | `AsyncIterator[DataFrame]` | Stream pages |
| `get_by_key(endpoint, key, ...)` | `dict` | Fetch by primary key |
| `get_by_id(endpoint, system_id, ...)` | `dict` | Fetch by SystemId |
| `count(endpoint, ...)` | `int` | Get record count |
| `get_first(endpoint, ...)` | `dict \| None` | Get first match |
| `exists(endpoint, key)` | `bool` | Check existence |
| `get_all(endpoint, ...)` | `DataFrame` | Optimized full fetch |
| `get_batch(endpoint, field, values, ...)` | `DataFrame` | Batch fetch by values |
| `get_since(endpoint, timestamp, ...)` | `DataFrame` | Delta sync (after) |
| `get_before(endpoint, timestamp, ...)` | `DataFrame` | Delta sync (before) |
| `get_endpoints()` | `list[str]` | List available endpoints |

### ODataQuery Methods

| Method | Description |
|--------|-------------|
| `.select(*fields)` | Select specific fields |
| `.filter(expression)` | Add filter (ANDed) |
| `.filter_raw(odata_str)` | Add raw OData filter |
| `.expand(*relations)` | Expand navigation properties |
| `.order_by(*fields)` | Set sort order |
| `.top(n)` | Limit results |
| `.skip(n)` | Skip first n records |
| `.build()` | Generate URL parameters |

### Field Operators

| Operator | OData | Example |
|----------|-------|---------|
| `==` | `eq` | `F.Status == "Active"` |
| `!=` | `ne` | `F.Status != "Blocked"` |
| `>` | `gt` | `F.Balance > 1000` |
| `>=` | `ge` | `F.Balance >= 1000` |
| `<` | `lt` | `F.Balance < 500` |
| `<=` | `le` | `F.Balance <= 500` |
| `&` | `and` | `(F.A > 1) & (F.B < 2)` |
| `\|` | `or` | `(F.A == 1) \| (F.A == 2)` |
| `.is_in()` | `or` chain | `F.No.is_in(["A", "B"])` |
