# Odyn - Complete LLM Reference

This document provides exhaustive documentation for Odyn, a Python client for Microsoft Dynamics 365 Business Central on-premises OData Web Services. An LLM with this context should be able to answer any question about Odyn usage, troubleshoot issues, and write correct code.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Business Central OData Fundamentals](#business-central-odata-fundamentals)
5. [Authentication](#authentication)
6. [Client Configuration](#client-configuration)
7. [Data Fetching Methods](#data-fetching-methods)
8. [Query Building](#query-building)
9. [Caching System](#caching-system)
10. [Progress Tracking](#progress-tracking)
11. [Request/Response Hooks](#requestresponse-hooks)
12. [Error Handling](#error-handling)
13. [Synchronous Client](#synchronous-client)
14. [Data Types and Conversions](#data-types-and-conversions)
15. [Performance Optimization](#performance-optimization)
16. [Complete Workflow Examples](#complete-workflow-examples)
17. [Troubleshooting Guide](#troubleshooting-guide)
18. [API Reference Tables](#api-reference-tables)

---

## Overview

Odyn is an async-first Python library for extracting data from Microsoft Dynamics 365 Business Central on-premises installations via OData V4 Web Services. It is designed for data engineering workflows where you need to pull large amounts of data reliably.

### Key Characteristics

- **Async-first**: Built on `httpx` and `asyncio` for non-blocking I/O
- **Polars DataFrames**: Returns data as Polars DataFrames (not pandas) for memory efficiency
- **Auto-pagination**: Automatically follows `@odata.nextLink` to fetch all pages
- **Resilient**: Exponential backoff retries, rate limiting, connection pooling
- **Cached**: Optional Parquet-based caching with TTL
- **Type-safe queries**: Fluent builder with operator overloading for filters

### What Odyn Does NOT Do

- Does not support OData WRITE operations (POST, PATCH, DELETE)
- Does not support OAuth/Azure AD authentication (on-premises Basic Auth only)
- Does not support Business Central SaaS (cloud) - only on-premises
- Does not return pandas DataFrames directly (use `.to_pandas()` to convert)

### Dependencies

```
httpx>=0.27.0      # Async HTTP client
polars>=1.0.0      # DataFrame library
aiolimiter>=1.2.1  # Token bucket rate limiting
```

---

## Architecture

### Component Overview

```
BCWebServiceClient
├── httpx.AsyncClient          # Connection pooling, HTTP/2 support
├── AsyncLimiter (aiolimiter)  # Token bucket rate limiting
├── asyncio.Semaphore          # Concurrency control
├── ParquetCache (optional)    # Disk-based DataFrame caching
└── ODataQuery                 # Query builder
```

### Request Flow

1. User calls `client.get("customers")`
2. ODataQuery builds URL parameters (`$select`, `$filter`, etc.)
3. Cache check: If enabled, check for valid cached response
4. If cache miss:
   a. Acquire semaphore (concurrency limit)
   b. Acquire rate limit token
   c. Call `on_request` hook if configured
   d. Send HTTP GET request
   e. Call `on_response` hook if configured
   f. Parse JSON response
   g. If `@odata.nextLink` exists and pagination enabled, repeat for next page
   h. Convert to Polars DataFrame
   i. Store in cache if enabled
5. Return DataFrame

### Rate Limiting Implementation

Odyn uses the token bucket algorithm via `aiolimiter`:

- Bucket fills at `requests_per_minute / 60` tokens per second
- Each request consumes 1 token
- `max_burst` controls bucket capacity (max tokens that can accumulate)
- Default: 550 req/min with burst = 4

The rate limiter is checked INSIDE the semaphore to prevent queued requests from all firing simultaneously when the semaphore releases.

### Retry Logic

Retries occur for:
- HTTP 429 (Too Many Requests)
- HTTP 5xx (Server errors)
- Connection timeouts
- Network errors

Retry delays use exponential backoff: `retry_backoff * (2 ** attempt)`

Example with `retry_backoff=1.0, max_retries=3`:
- Attempt 1: immediate
- Attempt 2: wait 1 second
- Attempt 3: wait 2 seconds
- Attempt 4: wait 4 seconds
- Then raise `RetryExhaustedError`

---

## Installation

```bash
# Using pip
pip install odyn

# Using uv (recommended)
uv add odyn

# From source
git clone https://github.com/yourusername/odyn.git
cd odyn
uv sync
```

### Verify Installation

```python
import odyn
print(odyn.__version__)  # e.g., "0.4.0"
```

---

## Business Central OData Fundamentals

Understanding how Business Central exposes OData is essential for using Odyn effectively.

### URL Structure

Business Central OData URLs follow this pattern:

```
https://{server}:{port}/{instance}/ODataV4/Company('{company}')/{endpoint}
```

Components:
- `server`: Hostname or IP (e.g., `bc-server.local`, `192.168.1.100`)
- `port`: Usually `7048` for OData (7047 is SOAP)
- `instance`: BC instance name (e.g., `BC210`, `BC230`, `Production`)
- `company`: URL-encoded company name
- `endpoint`: The published web service name

**Examples:**

```
# Without company (uses default company)
https://bc-server:7048/BC210/ODataV4/customers

# With company
https://bc-server:7048/BC210/ODataV4/Company('CRONUS%20International%20Ltd.')/customers

# With query parameters
https://bc-server:7048/BC210/ODataV4/Company('CRONUS')/customers?$select=No,Name&$filter=Balance gt 1000
```

### How to Find Endpoint Names

In Business Central:
1. Search for "Web Services" page
2. Look at the "Service Name" column - this is the endpoint name
3. The "Object Type" shows if it's a Page, Query, or Codeunit
4. "Published" must be checked for the endpoint to work

**Important:** Endpoint names are CASE-SENSITIVE. If BC shows `customerCard`, you must use exactly `customerCard`, not `CustomerCard` or `customercard`.

### Field Naming Conventions

Business Central applies these transformations to field names in OData:

1. **Spaces become underscores**: `"Balance (LCY)"` → `Balance_LCY`
2. **Special characters removed**: `"Balance %"` → `Balance_percent` or `Balance`
3. **Parentheses removed**: `"Amount (FCY)"` → `Amount_FCY`
4. **Periods removed**: `"No."` → `No`

**Common BC field name mappings:**

| BC Field | OData Field |
|----------|-------------|
| No. | `No` |
| Name | `Name` |
| Balance (LCY) | `Balance_LCY` |
| Credit Limit (LCY) | `Credit_Limit_LCY` |
| Salesperson Code | `Salesperson_Code` |
| Gen. Bus. Posting Group | `Gen_Bus_Posting_Group` |
| VAT Bus. Posting Group | `VAT_Bus_Posting_Group` |
| Customer Posting Group | `Customer_Posting_Group` |
| Bill-to Customer No. | `Bill_to_Customer_No` |
| Sell-to Customer No. | `Sell_to_Customer_No` |
| Document Type | `Document_Type` |
| Document No. | `Document_No` |
| Posting Date | `Posting_Date` |
| Entry No. | `Entry_No` |
| SystemId | `SystemId` (GUID, always present) |
| SystemCreatedAt | `SystemCreatedAt` (timestamp) |
| SystemModifiedAt | `SystemModifiedAt` (timestamp) |

### System Fields

Every BC record has these system fields (BC 15.0+):

- `SystemId`: GUID uniquely identifying the record
- `SystemCreatedAt`: UTC timestamp when record was created
- `SystemModifiedAt`: UTC timestamp when record was last modified
- `SystemCreatedBy`: GUID of user who created the record
- `SystemModifiedBy`: GUID of user who last modified the record

These are essential for delta synchronization.

### OData Pagination

BC limits response size. When there are more records than can fit in one response, BC returns:

```json
{
  "@odata.context": "...",
  "value": [ ...records... ],
  "@odata.nextLink": "https://bc-server:7048/BC210/ODataV4/customers?$skiptoken=..."
}
```

The `@odata.nextLink` contains a `$skiptoken` that BC uses internally to track position. Odyn automatically follows these links until:
- No more `@odata.nextLink` is present
- `max_pages` limit is reached

**Page size:** BC typically returns 1000-5000 records per page depending on configuration and record size.

### Common BC Endpoints

| Endpoint | Description |
|----------|-------------|
| `customers` | Customer master data |
| `vendors` | Vendor master data |
| `items` | Item master data |
| `salesOrders` | Sales order headers |
| `salesOrderLines` | Sales order lines |
| `salesInvoices` | Posted sales invoice headers |
| `salesInvoiceLines` | Posted sales invoice lines |
| `purchaseOrders` | Purchase order headers |
| `purchaseOrderLines` | Purchase order lines |
| `generalLedgerEntries` | G/L entries |
| `customerLedgerEntries` | Customer ledger entries |
| `vendorLedgerEntries` | Vendor ledger entries |
| `itemLedgerEntries` | Item ledger entries |
| `bankAccounts` | Bank account master data |
| `currencies` | Currency master data |
| `countries` | Country/region master data |
| `paymentTerms` | Payment terms |
| `shipmentMethods` | Shipment methods |

**Note:** Actual endpoint names depend on what's published in your BC instance. The above are common names but may vary.

---

## Authentication

### BasicAuth

Odyn uses HTTP Basic Authentication for on-premises Business Central:

```python
from odyn import BasicAuth

# Simple username/password
auth = BasicAuth("username", "password")

# With Windows domain (NTLM-style)
auth = BasicAuth("DOMAIN\\username", "password")
# or
auth = BasicAuth("DOMAIN/username", "password")  # Forward slash also works
```

### Password Types

Depending on BC configuration, you may need:

1. **Windows Password**: Your Windows domain password
2. **Web Service Access Key**: A special key generated in BC
   - In BC, go to Users page
   - Find your user, look for "Web Service Access Key" field
   - If empty, use "Change Web Service Key" action to generate one

### BasicAuth Internals

The `BasicAuth` class:
- Stores username and password
- Provides `auth_header` property returning Base64-encoded `Authorization` header value
- Masks password in `__repr__` for safe logging

```python
auth = BasicAuth("user", "secret123")
print(auth)  # BasicAuth(username='user', password='***')
print(auth.auth_header)  # 'dXNlcjpzZWNyZXQxMjM='
```

---

## Client Configuration

### BCWebServiceClient.create() - Complete Reference

```python
from odyn import BCWebServiceClient, BasicAuth
import logging

client = BCWebServiceClient.create(
    # === Required Parameters ===
    server="https://bc-server:7048",  # BC server URL with protocol and port
    instance="BC210",                  # BC instance name
    auth=BasicAuth("user", "pass"),    # Authentication

    # === Optional: Scope ===
    company="CRONUS International Ltd.",  # Company name (None = default company)

    # === Optional: Timeouts ===
    timeout=30.0,  # Request timeout in seconds (default: 30.0)

    # === Optional: Pagination ===
    max_pages=100,  # Max pages to fetch in auto-pagination (default: 100)
                    # Set higher for large datasets, lower to limit data

    # === Optional: SSL ===
    verify_ssl=True,  # Verify SSL certificates (default: True)
                      # Set False for self-signed certs (dev/internal only)

    # === Optional: Caching ===
    cache_dir="/path/to/cache",  # Directory for Parquet cache files (default: None = disabled)
    cache_ttl=3600,              # Cache time-to-live in seconds (default: None = forever)

    # === Optional: Logging ===
    log_level=logging.INFO,  # Logging level (default: logging.INFO)
                             # Use logging.DEBUG for verbose output

    # === Optional: Retry Behavior ===
    max_retries=3,      # Max retry attempts (default: 3)
    retry_backoff=1.0,  # Base delay for exponential backoff (default: 1.0)
                        # Delays: 1s, 2s, 4s, 8s, ...

    # === Optional: Concurrency & Rate Limiting ===
    max_connections=4,         # Max concurrent connections (default: 4)
    requests_per_minute=550.0, # Rate limit (default: 550.0, None = disabled)
    max_burst=4,               # Max burst size (default: max_connections)
                               # Controls token bucket capacity

    # === Optional: Hooks ===
    on_request=None,   # Callable(method, url, params) called before each request
    on_response=None,  # Callable(method, url, status_code, duration_ms) called after
)
```

### Parameter Deep Dive

#### server

The base URL of your Business Central server:

```python
# Standard HTTPS
server="https://bc-server:7048"

# With IP address
server="https://192.168.1.100:7048"

# With custom port
server="https://bc-server:8048"

# HTTP (not recommended, only for testing)
server="http://bc-server:7048"
```

#### instance

The BC instance name. Find this in BC Server Administration or the URL you use to access BC:

```python
instance="BC210"      # Business Central 21.0
instance="BC230"      # Business Central 23.0
instance="Production" # Custom instance name
instance="Test"       # Test instance
```

#### company

If your BC has multiple companies, specify which one:

```python
# Use default company
company=None

# Specify company (must match exactly, including spaces)
company="CRONUS International Ltd."
company="My Company"
```

The company name is URL-encoded automatically. Spaces, special characters, etc. are handled.

#### timeout

Total time allowed for a single HTTP request (not including retries):

```python
timeout=30.0   # Default: 30 seconds
timeout=60.0   # For slow servers
timeout=120.0  # For very large responses
```

If a request takes longer than this, it will timeout and potentially retry.

#### max_pages

Safety limit for auto-pagination:

```python
max_pages=100   # Default: stop after 100 pages
max_pages=1000  # For very large datasets
max_pages=1     # Fetch single page only (same as paginate=False in get())
```

With typical page sizes of 1000-5000 records, `max_pages=100` allows 100,000-500,000 records.

#### verify_ssl

```python
verify_ssl=True   # Default: verify SSL certificates
verify_ssl=False  # Skip verification (ONLY for self-signed certs in dev/internal)
```

**Warning:** Never disable SSL verification in production or when connecting over untrusted networks.

#### cache_dir and cache_ttl

```python
# Disable caching (default)
cache_dir=None

# Enable with default TTL (cache forever until manually cleared)
cache_dir="~/.cache/odyn"
cache_ttl=None

# Enable with 1-hour TTL
cache_dir="~/.cache/odyn"
cache_ttl=3600

# Enable with 24-hour TTL
cache_dir="/var/cache/odyn"
cache_ttl=86400
```

Cache files are stored as Parquet with SHA256-hashed filenames based on the full request URL and parameters.

#### max_retries and retry_backoff

```python
# Default: 3 retries with 1-second base delay
max_retries=3
retry_backoff=1.0
# Delays: 1s, 2s, 4s

# More aggressive: 5 retries with 2-second base
max_retries=5
retry_backoff=2.0
# Delays: 2s, 4s, 8s, 16s, 32s

# Less aggressive: 2 retries with 0.5-second base
max_retries=2
retry_backoff=0.5
# Delays: 0.5s, 1s
```

#### max_connections

Controls the connection pool size and maximum concurrent requests:

```python
max_connections=4   # Default: up to 4 concurrent requests
max_connections=1   # Sequential requests only
max_connections=10  # Higher concurrency (may overwhelm BC server)
```

**Recommendation:** Keep at 4 or lower. BC servers often struggle with high concurrency.

#### requests_per_minute

Rate limiting to avoid overwhelming the server or hitting BC's built-in limits:

```python
requests_per_minute=550.0  # Default: ~9.2 requests/second
requests_per_minute=300.0  # Conservative: 5 requests/second
requests_per_minute=60.0   # Very conservative: 1 request/second
requests_per_minute=None   # Disable rate limiting (not recommended)
```

#### max_burst

Controls the token bucket capacity:

```python
max_burst=None  # Default: same as max_connections
max_burst=1     # No bursting, strict rate limit
max_burst=10    # Allow bursts of up to 10 requests
```

Lower values prevent request storms on startup.

### Client Lifecycle

#### Context Manager (Recommended)

```python
async with BCWebServiceClient.create(...) as client:
    df = await client.get("customers")
# Client automatically closed, connections released
```

#### Manual Management

```python
client = BCWebServiceClient.create(...)

try:
    df = await client.get("customers")
finally:
    await client.close()
```

#### Long-Running Applications

For applications that need to make requests over time:

```python
# Create once at startup
client = BCWebServiceClient.create(...)

# Use throughout application lifetime
async def handle_request():
    return await client.get("customers")

# Close on shutdown
async def shutdown():
    await client.close()
```

---

## Data Fetching Methods

### get() - Primary Data Fetching

```python
async def get(
    endpoint: str,                           # Required: OData entity set name
    *,
    query: ODataQuery | None = None,         # Optional: Query builder instance
    paginate: bool = True,                   # Auto-fetch all pages?
    use_cache: bool = True,                  # Use cache if available?
    on_progress: ProgressCallback | None = None,  # Progress callback
) -> polars.DataFrame
```

**Basic usage:**

```python
# Fetch all customers
customers = await client.get("customers")

# Fetch with query
from odyn.query import ODataQuery, F
query = ODataQuery().filter(F.Balance_LCY > 1000).select("No", "Name", "Balance_LCY")
customers = await client.get("customers", query=query)

# Single page only
first_page = await client.get("customers", paginate=False)

# Skip cache (always fetch fresh)
fresh = await client.get("customers", use_cache=False)
```

**Return value:**

Always returns a `polars.DataFrame`. If no records found, returns an empty DataFrame with the expected schema.

```python
df = await client.get("customers")
print(type(df))       # <class 'polars.dataframe.frame.DataFrame'>
print(len(df))        # Number of rows
print(df.columns)     # List of column names
print(df.schema)      # Dict of column name -> dtype
```

### get_stream() - Memory-Efficient Streaming

For datasets too large to fit in memory:

```python
async def get_stream(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
    on_progress: ProgressCallback | None = None,
) -> AsyncIterator[polars.DataFrame]
```

**Usage:**

```python
# Process page by page
total_rows = 0
async for page_df in client.get_stream("itemLedgerEntries"):
    # Each page_df is a Polars DataFrame
    process_page(page_df)
    total_rows += len(page_df)

print(f"Processed {total_rows} rows")

# Write directly to Parquet files
page_num = 0
async for page_df in client.get_stream("largeDataset"):
    page_df.write_parquet(f"output/page_{page_num:04d}.parquet")
    page_num += 1

# Filter while streaming
query = ODataQuery().filter(F.Amount > 0).select("Entry_No", "Amount", "Posting_Date")
async for page_df in client.get_stream("generalLedgerEntries", query=query):
    yield page_df
```

**Note:** `get_stream()` always bypasses the cache (each page is fetched fresh).

### get_by_key() - Single Record by Primary Key

```python
async def get_by_key(
    endpoint: str,              # Entity set name
    key: str,                   # Primary key value
    *,
    select: list[str] | None = None,  # Fields to return
) -> dict[str, Any]
```

**Usage:**

```python
# Get customer by No
customer = await client.get_by_key("customers", "10000")
print(customer["Name"])  # "CRONUS International Ltd."

# Get with specific fields only
customer = await client.get_by_key(
    "customers",
    "10000",
    select=["No", "Name", "Balance_LCY"]
)
# Returns: {"No": "10000", "Name": "...", "Balance_LCY": 1234.56}
```

**Raises:** `NotFoundError` if record doesn't exist.

### get_by_id() - Single Record by SystemId

```python
async def get_by_id(
    endpoint: str,
    system_id: str,             # GUID string
    *,
    select: list[str] | None = None,
) -> dict[str, Any]
```

**Usage:**

```python
# Get by GUID
customer = await client.get_by_id(
    "customers",
    "12345678-1234-1234-1234-123456789012"
)
```

**Raises:** `NotFoundError` if record doesn't exist.

### count() - Record Count

```python
async def count(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
) -> int
```

**Usage:**

```python
# Total customers
total = await client.count("customers")

# Customers with balance > 1000
query = ODataQuery().filter(F.Balance_LCY > 1000)
high_balance = await client.count("customers", query=query)

# Active items
query = ODataQuery().filter(F.Blocked == False)
active_items = await client.count("items", query=query)
```

**Implementation:** Uses OData `$count=true` parameter, doesn't fetch actual data.

### get_first() - First Matching Record

```python
async def get_first(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
) -> dict[str, Any] | None
```

**Usage:**

```python
# Get first customer
first = await client.get_first("customers")

# Get first matching record
query = ODataQuery().filter(F.Name == "CRONUS").select("No", "Name")
customer = await client.get_first("customers", query=query)

if customer:
    print(customer["No"])
else:
    print("Not found")
```

**Returns:** `None` if no records match.

### exists() - Check Existence

```python
async def exists(
    endpoint: str,
    key: str,
) -> bool
```

**Usage:**

```python
if await client.exists("customers", "10000"):
    print("Customer exists")
else:
    print("Customer not found")
```

**Implementation:** Uses HTTP HEAD request, minimal data transfer.

### get_all() - Optimized Full Fetch

```python
async def get_all(
    endpoint: str,
    *,
    batch_size: int = 1000,
) -> polars.DataFrame
```

Fetches all records with optimized batch size:

```python
# Get all items (may be millions)
all_items = await client.get_all("items", batch_size=2000)
```

**Difference from get():** `get_all()` uses `$top` to request larger pages, potentially reducing the number of round trips.

### get_batch() - Batch Fetch by Value List

```python
async def get_batch(
    endpoint: str,
    field: str,                              # Field to filter on
    values: list[Any],                       # Values to match
    *,
    batch_size: int = 50,                    # Values per request
    select: list[str] | None = None,
    expand: list[str] | None = None,
    order_by: list[str] | None = None,
    additional_filter: FilterExpression | None = None,
    fail_fast: bool = False,                 # Raise on first error?
    use_cache: bool = True,
    on_progress: BatchProgressCallback | None = None,
) -> polars.DataFrame
```

Efficiently fetches records matching a large list of values by chunking into multiple concurrent requests:

```python
# Fetch 500 customers by their IDs
customer_ids = ["C001", "C002", ..., "C500"]

customers = await client.get_batch(
    endpoint="customers",
    field="No",
    values=customer_ids,
    batch_size=50,  # 50 IDs per request = 10 requests
    select=["No", "Name", "Balance_LCY"],
)
```

**With additional filter:**

```python
from odyn.query import F

# Only active customers from the list
active_customers = await client.get_batch(
    "customers",
    "No",
    customer_ids,
    additional_filter=(F.Blocked == False),
)
```

**Error handling:**

```python
# Continue on individual batch failures (default)
df = await client.get_batch("customers", "No", ids, fail_fast=False)

# Stop immediately on first failure
df = await client.get_batch("customers", "No", ids, fail_fast=True)
```

**How it works:**
1. Splits `values` into chunks of `batch_size`
2. Builds filter: `No eq 'C001' or No eq 'C002' or ...` for each chunk
3. Runs all chunk requests concurrently (respecting `max_connections`)
4. Merges all results into single DataFrame

### get_since() - Delta Sync (After Timestamp)

```python
async def get_since(
    endpoint: str,
    timestamp: str,                          # ISO 8601 timestamp
    *,
    query: ODataQuery | None = None,
    use_cache: bool = False,                 # Default: False for fresh data
    on_progress: ProgressCallback | None = None,
) -> polars.DataFrame
```

Fetch records modified after a timestamp:

```python
from datetime import datetime, timedelta, timezone

# Records modified in the last hour
one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
recent = await client.get_since("customers", one_hour_ago)

# Records modified since last sync
last_sync = "2024-01-15T10:30:00Z"
updates = await client.get_since("customers", last_sync)

# With additional query
query = ODataQuery().select("No", "Name", "SystemModifiedAt")
updates = await client.get_since("customers", last_sync, query=query)
```

**Implementation:** Adds filter `SystemModifiedAt gt '{timestamp}'`

### get_before() - Delta Sync (Before Timestamp)

```python
async def get_before(
    endpoint: str,
    timestamp: str,
    *,
    query: ODataQuery | None = None,
    use_cache: bool = True,                  # Default: True for historical data
    on_progress: ProgressCallback | None = None,
) -> polars.DataFrame
```

Fetch records NOT modified since a timestamp (stale records):

```python
# Records not modified in 30 days
thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
stale = await client.get_before("customers", thirty_days_ago)
```

**Implementation:** Adds filter `SystemModifiedAt lt '{timestamp}'`

### get_endpoints() - List Available Endpoints

```python
async def get_endpoints() -> list[str]
```

**Usage:**

```python
endpoints = await client.get_endpoints()
print(endpoints)
# ['customers', 'vendors', 'items', 'salesOrders', ...]
```

**Implementation:** Fetches OData service document and extracts entity set names.

---

## Query Building

### ODataQuery Class

Fluent builder for OData URL parameters:

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY", "City")
    .filter(F.Balance_LCY > 1000)
    .filter(F.Blocked == False)
    .expand("SalesLines")
    .order_by("Balance_LCY desc")
    .top(100)
    .skip(50)
)

df = await client.get("customers", query=query)
```

### Method Reference

#### select(*fields)

Specify which fields to return:

```python
# Single field
query = ODataQuery().select("No")

# Multiple fields
query = ODataQuery().select("No", "Name", "Balance_LCY")

# Using list unpacking
fields = ["No", "Name", "Balance_LCY"]
query = ODataQuery().select(*fields)
```

**OData output:** `$select=No,Name,Balance_LCY`

#### filter(expression)

Add a filter expression. Multiple calls are ANDed:

```python
# Single filter
query = ODataQuery().filter(F.Balance_LCY > 1000)

# Multiple filters (ANDed)
query = (
    ODataQuery()
    .filter(F.Balance_LCY > 1000)
    .filter(F.City == "Seattle")
)
# Output: $filter=Balance_LCY gt 1000 and City eq 'Seattle'
```

#### filter_raw(odata_string)

Add a raw OData filter string for expressions not supported by the builder:

```python
# Contains (substring search)
query = ODataQuery().filter_raw("contains(Name, 'Corp')")

# StartsWith
query = ODataQuery().filter_raw("startswith(Name, 'A')")

# EndsWith
query = ODataQuery().filter_raw("endswith(Email, '@example.com')")

# Date functions
query = ODataQuery().filter_raw("year(Posting_Date) eq 2024")

# Combine with builder filters
query = (
    ODataQuery()
    .filter(F.Balance_LCY > 0)
    .filter_raw("contains(Name, 'Corp')")
)
```

#### expand(*relations)

Expand navigation properties (related entities):

```python
# Single expand
query = ODataQuery().expand("SalesLines")

# Multiple expands
query = ODataQuery().expand("SalesLines", "ShipmentMethod")
```

**OData output:** `$expand=SalesLines,ShipmentMethod`

**Note:** Expand support depends on how the BC page/query is configured. Not all endpoints support expands.

#### order_by(*fields)

Set sort order:

```python
# Ascending (default)
query = ODataQuery().order_by("Name")

# Descending
query = ODataQuery().order_by("Balance_LCY desc")

# Multiple sort fields
query = ODataQuery().order_by("City asc", "Name asc")
```

**OData output:** `$orderby=Balance_LCY desc`

#### top(n)

Limit number of records:

```python
query = ODataQuery().top(10)  # First 10 records
```

**OData output:** `$top=10`

#### skip(n)

Skip first n records:

```python
query = ODataQuery().skip(100)  # Skip first 100
```

**OData output:** `$skip=100`

**Note:** For pagination, use auto-pagination or `get_stream()` instead of manual `skip()`.

#### count(include=True)

Include total count in response:

```python
query = ODataQuery().count(True)
```

**OData output:** `$count=true`

#### build()

Generate the URL parameters dictionary:

```python
query = ODataQuery().select("No", "Name").filter(F.Balance_LCY > 1000)
params = query.build()
# {'$select': 'No,Name', '$filter': 'Balance_LCY gt 1000'}
```

### F Proxy - Field Expressions

The `F` proxy creates `Field` objects via attribute access:

```python
from odyn.query import F

# These are equivalent:
F.Balance_LCY      # Field("Balance_LCY")
F.No               # Field("No")
F.Customer_Name    # Field("Customer_Name")
```

### Field Operators

#### Comparison Operators

| Python | OData | Example |
|--------|-------|---------|
| `==` | `eq` | `F.Status == "Active"` |
| `!=` | `ne` | `F.Status != "Blocked"` |
| `>` | `gt` | `F.Balance > 1000` |
| `>=` | `ge` | `F.Balance >= 1000` |
| `<` | `lt` | `F.Balance < 500` |
| `<=` | `le` | `F.Balance <= 500` |

#### Logical Operators

```python
# AND
(F.Balance > 1000) & (F.Status == "Active")
# Output: Balance gt 1000 and Status eq 'Active'

# OR
(F.City == "Seattle") | (F.City == "Portland")
# Output: City eq 'Seattle' or City eq 'Portland'

# Complex combinations
((F.Balance > 1000) & (F.Status == "Active")) | (F.Credit_Limit > 50000)
# Output: (Balance gt 1000 and Status eq 'Active') or Credit_Limit gt 50000
```

**Important:** Always use parentheses around individual comparisons when combining with `&` or `|`.

#### is_in() Method

Check if field value is in a list:

```python
# Customer numbers in a list
F.No.is_in(["C001", "C002", "C003"])
# Output: No eq 'C001' or No eq 'C002' or No eq 'C003'

# Document types
F.Document_Type.is_in(["Invoice", "Credit Memo"])
# Output: Document_Type eq 'Invoice' or Document_Type eq 'Credit Memo'
```

**Warning:** For large lists (>20 values), use `client.get_batch()` instead to avoid URL length limits.

### Value Type Handling

The query builder automatically handles value types:

```python
# Strings: quoted
F.Name == "John"           # Name eq 'John'

# Numbers: unquoted
F.Balance > 1000           # Balance gt 1000
F.Balance > 1000.50        # Balance gt 1000.5

# Booleans: lowercase
F.Blocked == True          # Blocked eq true
F.Blocked == False         # Blocked eq false

# None/null
F.Email == None            # Email eq null
```

### Date and DateTime Filters

OData dates must be in ISO 8601 format:

```python
# Date comparison (use raw filter)
query = ODataQuery().filter_raw("Posting_Date ge 2024-01-01")

# DateTime comparison
query = ODataQuery().filter_raw("SystemModifiedAt gt 2024-01-15T10:30:00Z")

# Using Python datetime
from datetime import datetime, timezone
dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
query = ODataQuery().filter_raw(f"SystemModifiedAt gt {dt.isoformat()}")
```

### Complete Query Examples

```python
from odyn.query import ODataQuery, F

# Example 1: Top customers by balance
query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY", "Credit_Limit_LCY")
    .filter(F.Balance_LCY > 0)
    .filter(F.Blocked == False)
    .order_by("Balance_LCY desc")
    .top(100)
)

# Example 2: Recent sales invoices
query = (
    ODataQuery()
    .select("No", "Sell_to_Customer_Name", "Amount", "Posting_Date")
    .filter_raw("Posting_Date ge 2024-01-01")
    .filter(F.Amount > 1000)
    .order_by("Posting_Date desc")
)

# Example 3: Items in specific categories
query = (
    ODataQuery()
    .select("No", "Description", "Unit_Price", "Inventory")
    .filter(F.Item_Category_Code.is_in(["FURNITURE", "ELECTRONICS"]))
    .filter(F.Inventory > 0)
    .order_by("Description")
)

# Example 4: Complex OR conditions
query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY", "City")
    .filter(
        ((F.City == "Seattle") | (F.City == "Portland"))
        & (F.Balance_LCY > 5000)
    )
)
```

---

## Caching System

### How Caching Works

1. **Key Generation:** SHA256 hash of full URL (including parameters)
2. **Storage:** Parquet files in `cache_dir`
3. **Metadata:** JSON sidecar file with URL, timestamp, TTL
4. **Validation:** Check TTL on read, return None if expired

### Enable Caching

```python
client = BCWebServiceClient.create(
    ...,
    cache_dir="~/.cache/odyn",  # Any writable directory
    cache_ttl=3600,             # 1 hour TTL (optional)
)
```

### Cache Behavior by Method

| Method | Uses Cache | Updates Cache |
|--------|-----------|---------------|
| `get()` | Yes (if `use_cache=True`) | Yes |
| `get_stream()` | No | No |
| `get_by_key()` | No | No |
| `get_by_id()` | No | No |
| `count()` | No | No |
| `get_first()` | No | No |
| `exists()` | No | No |
| `get_all()` | Yes | Yes |
| `get_batch()` | Yes (per batch) | Yes |
| `get_since()` | No (default) | Optional |
| `get_before()` | Yes (default) | Yes |

### Cache Management Methods

```python
# Get statistics
stats = client.cache_stats
if stats:
    print(f"Hits: {stats['hits']}")
    print(f"Misses: {stats['misses']}")
    print(f"Disk usage: {stats['disk_bytes']} bytes")

# Number of cached entries
count = client.cache_size

# Remove expired entries only
removed = client.cleanup_cache()
print(f"Removed {removed} expired entries")

# Clear all cache
removed = client.clear_cache()
print(f"Cleared {removed} entries")
```

### Cache File Structure

```
~/.cache/odyn/
├── a1b2c3d4e5f6...abc.parquet       # Cached DataFrame
├── a1b2c3d4e5f6...abc.parquet.json  # Metadata
├── f6e5d4c3b2a1...def.parquet
├── f6e5d4c3b2a1...def.parquet.json
└── ...
```

Metadata JSON example:

```json
{
  "url": "https://bc-server:7048/BC210/ODataV4/customers?$select=No,Name",
  "created_at": "2024-01-15T10:30:00.123456",
  "ttl": 3600,
  "params": {"$select": "No,Name"}
}
```

### Using ParquetCache Directly

```python
from odyn.cache import ParquetCache
from pathlib import Path
import polars as pl

cache = ParquetCache(Path("./my_cache"))

# Store a DataFrame
df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
cache.set("my_key", df, url="https://example.com", ttl=3600)

# Retrieve
cached_df = cache.get("my_key")
if cached_df is not None:
    print(cached_df)

# Check stats
print(cache.stats())  # {"hits": 1, "misses": 0, "disk_bytes": 1234}

# Delete specific entry
cache.delete("my_key")

# Clear all
cache.clear()
```

---

## Progress Tracking

### ProgressCallback Protocol

For `get()`, `get_stream()`, `get_since()`, `get_before()`:

```python
def on_progress(
    *,
    page: int,              # Current page number (1-indexed)
    records_on_page: int,   # Records fetched in this page
    total_records: int,     # Cumulative records fetched so far
    is_final: bool,         # True if this is the last page
) -> None:
    ...
```

**Example:**

```python
def my_progress(*, page, records_on_page, total_records, is_final):
    if is_final:
        print(f"Complete! Fetched {total_records} records in {page} pages")
    else:
        print(f"Page {page}: {records_on_page} records ({total_records} total)")

df = await client.get("customers", on_progress=my_progress)
```

**Output:**

```
Page 1: 1000 records (1000 total)
Page 2: 1000 records (2000 total)
Page 3: 456 records (2456 total)
Complete! Fetched 2456 records in 3 pages
```

### BatchProgressCallback Protocol

For `get_batch()`:

```python
def on_batch_progress(
    *,
    batch: int,           # Current batch number (1-indexed)
    total_batches: int,   # Total number of batches
    successful: int,      # Batches completed successfully
    failed: int,          # Batches that failed
    is_final: bool,       # True when all batches complete
) -> None:
    ...
```

**Example:**

```python
def my_batch_progress(*, batch, total_batches, successful, failed, is_final):
    pct = batch / total_batches * 100
    print(f"[{pct:5.1f}%] Batch {batch}/{total_batches} | OK: {successful} | Failed: {failed}")

df = await client.get_batch(
    "customers",
    "No",
    customer_ids,  # 500 IDs
    batch_size=50, # 10 batches
    on_progress=my_batch_progress,
)
```

**Output:**

```
[ 10.0%] Batch 1/10 | OK: 1 | Failed: 0
[ 20.0%] Batch 2/10 | OK: 2 | Failed: 0
...
[100.0%] Batch 10/10 | OK: 10 | Failed: 0
```

### Progress with tqdm

```python
from tqdm import tqdm

# For pagination
pbar = None
def tqdm_progress(*, page, records_on_page, total_records, is_final):
    global pbar
    if pbar is None:
        pbar = tqdm(desc="Fetching", unit=" records")
    pbar.update(records_on_page)
    if is_final:
        pbar.close()

df = await client.get("customers", on_progress=tqdm_progress)

# For batch operations
def tqdm_batch_progress(*, batch, total_batches, successful, failed, is_final):
    if batch == 1:
        global pbar
        pbar = tqdm(total=total_batches, desc="Batches", unit="batch")
    pbar.update(1)
    if is_final:
        pbar.close()

df = await client.get_batch(..., on_progress=tqdm_batch_progress)
```

---

## Request/Response Hooks

### RequestHook Protocol

Called before each HTTP request:

```python
def on_request(
    *,
    method: str,                    # HTTP method ("GET")
    url: str,                       # Full URL
    params: dict[str, str] | None,  # Query parameters
) -> None:
    ...
```

### ResponseHook Protocol

Called after each HTTP response:

```python
def on_response(
    *,
    method: str,          # HTTP method ("GET")
    url: str,             # Full URL
    status_code: int,     # HTTP status code
    duration_ms: float,   # Request duration in milliseconds
) -> None:
    ...
```

### Hook Examples

**Simple logging:**

```python
def log_request(*, method, url, params):
    print(f">> {method} {url}")
    if params:
        print(f"   Params: {params}")

def log_response(*, method, url, status_code, duration_ms):
    print(f"<< {status_code} in {duration_ms:.0f}ms")

client = BCWebServiceClient.create(
    ...,
    on_request=log_request,
    on_response=log_response,
)
```

**Metrics collection:**

```python
from collections import defaultdict
import time

metrics = {
    "total_requests": 0,
    "total_duration_ms": 0,
    "status_codes": defaultdict(int),
    "endpoints": defaultdict(int),
}

def collect_request(*, method, url, params):
    # Extract endpoint from URL
    endpoint = url.split("/")[-1].split("?")[0]
    metrics["endpoints"][endpoint] += 1

def collect_response(*, method, url, status_code, duration_ms):
    metrics["total_requests"] += 1
    metrics["total_duration_ms"] += duration_ms
    metrics["status_codes"][status_code] += 1

# After running queries:
print(f"Total requests: {metrics['total_requests']}")
print(f"Avg duration: {metrics['total_duration_ms'] / metrics['total_requests']:.0f}ms")
print(f"Status codes: {dict(metrics['status_codes'])}")
print(f"Endpoints: {dict(metrics['endpoints'])}")
```

**Structured logging:**

```python
import logging
import json

logger = logging.getLogger("odyn.http")

def structured_request(*, method, url, params):
    logger.info(json.dumps({
        "event": "request",
        "method": method,
        "url": url,
        "params": params,
    }))

def structured_response(*, method, url, status_code, duration_ms):
    logger.info(json.dumps({
        "event": "response",
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }))
```

---

## Error Handling

### Exception Hierarchy

```
OdynError (base class for all Odyn exceptions)
│
├── OdynConnectionError (network-level failures)
│   ├── OdynTimeoutError (request timed out)
│   └── OdynSSLError (SSL certificate verification failed)
│
├── WebServiceError (HTTP error responses from BC)
│   ├── AuthenticationError (HTTP 401)
│   ├── ForbiddenError (HTTP 403)
│   ├── NotFoundError (HTTP 404)
│   ├── ValidationError (HTTP 400)
│   ├── RateLimitError (HTTP 429)
│   └── ServerError (HTTP 5xx)
│
├── RetryExhaustedError (all retry attempts failed)
│
└── QueryValidationError (invalid OData query construction)
```

### WebServiceError Attributes

All `WebServiceError` subclasses have:

```python
exception.message        # str: Error message
exception.status_code    # int: HTTP status code
exception.url           # str: Request URL
exception.response_body # str: Raw response body
exception.odata_error   # dict | None: Parsed OData error object
```

**OData error structure:**

```python
{
    "error": {
        "code": "BadRequest",
        "message": "Invalid filter expression"
    }
}
```

### RetryExhaustedError Attributes

```python
exception.message        # str: Error description
exception.attempts       # int: Number of attempts made
exception.last_exception # Exception: The last exception that occurred
```

### Handling Patterns

**Basic error handling:**

```python
from odyn.exceptions import (
    NotFoundError,
    AuthenticationError,
    RetryExhaustedError,
    WebServiceError,
    OdynError,
)

try:
    customer = await client.get_by_key("customers", "INVALID")
except NotFoundError:
    print("Customer not found")
except AuthenticationError:
    print("Check your credentials")
except RetryExhaustedError as e:
    print(f"Failed after {e.attempts} attempts: {e.last_exception}")
except WebServiceError as e:
    print(f"BC returned error {e.status_code}: {e.message}")
except OdynError as e:
    print(f"Odyn error: {e}")
```

**Graceful degradation:**

```python
async def get_customer_safe(client, customer_no):
    """Get customer or return None if not found."""
    try:
        return await client.get_by_key("customers", customer_no)
    except NotFoundError:
        return None

customer = await get_customer_safe(client, "C001")
if customer:
    process(customer)
```

**Retry with different parameters:**

```python
async def fetch_with_fallback(client, endpoint):
    """Try normal fetch, fall back to smaller batches if rate limited."""
    try:
        return await client.get(endpoint)
    except RateLimitError:
        # Rate limited, try streaming instead
        frames = []
        async for page in client.get_stream(endpoint):
            frames.append(page)
            await asyncio.sleep(1)  # Extra delay between pages
        return pl.concat(frames)
```

**Logging errors:**

```python
import logging

logger = logging.getLogger(__name__)

try:
    df = await client.get("customers")
except WebServiceError as e:
    logger.error(
        "BC request failed",
        extra={
            "status_code": e.status_code,
            "url": e.url,
            "odata_error": e.odata_error,
        }
    )
    raise
```

---

## Synchronous Client

### BCWebServiceClientSync

For non-async contexts (scripts, notebooks, Django views, etc.):

```python
from odyn import BCWebServiceClientSync, BasicAuth

# Context manager (recommended)
with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
) as client:
    # All methods are blocking (no await)
    customers = client.get("customers")
    print(len(customers))

# Manual management
client = BCWebServiceClientSync.create(...)
try:
    customers = client.get("customers")
finally:
    client.close()
```

### Available Methods

All methods mirror the async client but block until completion:

```python
# Data fetching
df = client.get("customers")
df = client.get("customers", query=query, paginate=True, use_cache=True)

# Single record
record = client.get_by_key("customers", "10000")
record = client.get_by_id("customers", "guid-here")

# Queries
count = client.count("customers")
first = client.get_first("customers", query=query)
exists = client.exists("customers", "10000")

# Batch operations
df = client.get_all("customers", batch_size=1000)
df = client.get_batch("customers", "No", ["C001", "C002"])

# Delta sync
df = client.get_since("customers", "2024-01-01T00:00:00Z")
df = client.get_before("customers", "2024-01-01T00:00:00Z")

# Metadata
endpoints = client.get_endpoints()

# Cache management
stats = client.cache_stats
size = client.cache_size
client.cleanup_cache()
client.clear_cache()
```

### NOT Available in Sync Client

- `get_stream()` - No sync equivalent (use `get()` with pagination)

### How It Works

The sync client:
1. Creates a background thread with its own event loop
2. Submits coroutines to that loop via `asyncio.run_coroutine_threadsafe()`
3. Blocks the calling thread until the coroutine completes
4. Returns the result

This allows sync code to use the async client without blocking the async machinery.

### Use in Jupyter Notebooks

```python
# Jupyter has its own event loop, so use sync client
from odyn import BCWebServiceClientSync, BasicAuth

client = BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
)

# Fetch data
customers = client.get("customers")
customers.head()

# Don't forget to close when done
client.close()
```

---

## Data Types and Conversions

### BC to Polars Type Mapping

| BC/OData Type | Polars Type | Notes |
|---------------|-------------|-------|
| Edm.String | `pl.Utf8` | Text fields |
| Edm.Int32 | `pl.Int32` | Integer fields |
| Edm.Int64 | `pl.Int64` | BigInteger fields |
| Edm.Decimal | `pl.Float64` | Decimal/money fields |
| Edm.Double | `pl.Float64` | Float fields |
| Edm.Boolean | `pl.Boolean` | Yes/No fields |
| Edm.Date | `pl.Date` | Date fields |
| Edm.DateTimeOffset | `pl.Datetime` | DateTime fields |
| Edm.Guid | `pl.Utf8` | GUIDs as strings |
| Edm.Binary | `pl.Binary` | Binary data |

### Working with Polars DataFrames

```python
import polars as pl

# Fetch data
customers = await client.get("customers")

# Basic operations
print(customers.shape)        # (rows, cols)
print(customers.columns)      # Column names
print(customers.schema)       # Column types
print(customers.head(5))      # First 5 rows
print(customers.tail(5))      # Last 5 rows

# Filtering
active = customers.filter(pl.col("Blocked") == False)
high_balance = customers.filter(pl.col("Balance_LCY") > 1000)

# Sorting
sorted_df = customers.sort("Balance_LCY", descending=True)

# Selecting columns
subset = customers.select(["No", "Name", "Balance_LCY"])

# Adding computed columns
with_flag = customers.with_columns(
    (pl.col("Balance_LCY") > 10000).alias("high_value")
)

# Aggregations
total_balance = customers["Balance_LCY"].sum()
avg_balance = customers["Balance_LCY"].mean()
by_city = customers.group_by("City").agg(
    pl.col("Balance_LCY").sum().alias("total_balance"),
    pl.len().alias("customer_count"),
)

# Iteration
for row in customers.iter_rows(named=True):
    print(row["No"], row["Name"])
```

### Converting to Other Formats

```python
# To pandas
pandas_df = customers.to_pandas()

# To dictionary
records = customers.to_dicts()  # List of dicts
# [{"No": "10000", "Name": "...", ...}, ...]

# To CSV
customers.write_csv("customers.csv")

# To Parquet
customers.write_parquet("customers.parquet")

# To JSON
customers.write_json("customers.json")

# To Excel (requires xlsxwriter)
customers.write_excel("customers.xlsx")
```

### Handling Null Values

```python
# Check for nulls
has_nulls = customers["Email"].null_count() > 0

# Fill nulls
filled = customers.with_columns(
    pl.col("Email").fill_null("no-email@example.com")
)

# Drop rows with nulls
no_nulls = customers.drop_nulls(subset=["Email"])

# Filter out nulls
with_email = customers.filter(pl.col("Email").is_not_null())
```

### Date/Time Operations

```python
# Parse dates
df = customers.with_columns(
    pl.col("SystemModifiedAt").str.to_datetime()
)

# Extract components
df = customers.with_columns(
    pl.col("SystemModifiedAt").dt.year().alias("year"),
    pl.col("SystemModifiedAt").dt.month().alias("month"),
    pl.col("SystemModifiedAt").dt.day().alias("day"),
)

# Filter by date
from datetime import date
recent = customers.filter(
    pl.col("SystemModifiedAt") > date(2024, 1, 1)
)
```

---

## Performance Optimization

### Reduce Data Transfer

```python
# Select only needed fields
query = ODataQuery().select("No", "Name", "Balance_LCY")
df = await client.get("customers", query=query)

# Filter server-side, not client-side
query = ODataQuery().filter(F.Balance_LCY > 1000)
df = await client.get("customers", query=query)
# Better than: df = await client.get("customers") then filter locally
```

### Use Caching for Static Data

```python
# Cache master data aggressively
client = BCWebServiceClient.create(
    ...,
    cache_dir="~/.cache/odyn",
    cache_ttl=86400,  # 24 hours for slowly-changing data
)

# Master data (cache hits)
customers = await client.get("customers")  # First call: ~500ms
customers = await client.get("customers")  # Second call: ~5ms

# Transactional data (skip cache)
invoices = await client.get("salesInvoices", use_cache=False)
```

### Streaming for Large Datasets

```python
# DON'T: Load everything into memory
all_entries = await client.get("itemLedgerEntries")  # May run out of memory

# DO: Stream and process
async for page in client.get_stream("itemLedgerEntries"):
    # Process each page
    process(page)
    # Or write to disk
    page.write_parquet(f"page_{i}.parquet")
```

### Batch Operations for ID Lists

```python
# DON'T: Fetch one by one
for customer_no in customer_list:
    customer = await client.get_by_key("customers", customer_no)

# DO: Batch fetch
customers = await client.get_batch("customers", "No", customer_list)
```

### Tune Rate Limiting

```python
# For fast BC servers
client = BCWebServiceClient.create(
    ...,
    requests_per_minute=550.0,  # Default
    max_connections=4,          # Default
)

# For slower/shared BC servers
client = BCWebServiceClient.create(
    ...,
    requests_per_minute=120.0,  # 2 req/sec
    max_connections=2,          # Less concurrent load
)
```

### Parallel Fetching

```python
import asyncio

# Fetch multiple endpoints in parallel
customers, vendors, items = await asyncio.gather(
    client.get("customers"),
    client.get("vendors"),
    client.get("items"),
)

# Parallel batch fetches
async def fetch_related(customer_ids):
    customers, invoices, ledger = await asyncio.gather(
        client.get_batch("customers", "No", customer_ids),
        client.get_batch("salesInvoices", "Sell_to_Customer_No", customer_ids),
        client.get_batch("customerLedgerEntries", "Customer_No", customer_ids),
    )
    return customers, invoices, ledger
```

---

## Complete Workflow Examples

### Example 1: Basic Data Extraction

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        company="CRONUS International Ltd.",
        auth=BasicAuth("DOMAIN\\user", "password"),
    ) as client:
        # Fetch customers
        customers = await client.get("customers")
        print(f"Fetched {len(customers)} customers")

        # Save to parquet
        customers.write_parquet("customers.parquet")

asyncio.run(main())
```

### Example 2: Filtered Query with Progress

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth
from odyn.query import ODataQuery, F

def show_progress(*, page, records_on_page, total_records, is_final):
    status = "Done!" if is_final else "..."
    print(f"Page {page}: {total_records} records {status}")

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("user", "pass"),
    ) as client:
        # Build query
        query = (
            ODataQuery()
            .select("No", "Name", "Balance_LCY", "City")
            .filter(F.Balance_LCY > 5000)
            .filter(F.Blocked == False)
            .order_by("Balance_LCY desc")
        )

        # Fetch with progress
        customers = await client.get("customers", query=query, on_progress=show_progress)

        # Process results
        for row in customers.head(10).iter_rows(named=True):
            print(f"{row['No']}: {row['Name']} - ${row['Balance_LCY']:,.2f}")

asyncio.run(main())
```

### Example 3: Delta Synchronization Pipeline

```python
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from odyn import BCWebServiceClient, BasicAuth

STATE_FILE = Path("sync_state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_sync": None}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

async def sync_customers(client, last_sync):
    """Fetch only customers modified since last sync."""
    if last_sync:
        print(f"Fetching customers modified since {last_sync}")
        df = await client.get_since("customers", last_sync)
    else:
        print("Initial sync: fetching all customers")
        df = await client.get("customers")

    return df

async def main():
    state = load_state()

    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("user", "pass"),
        cache_dir=None,  # No caching for delta sync
    ) as client:
        # Fetch updates
        customers = await sync_customers(client, state["last_sync"])

        if len(customers) > 0:
            print(f"Processing {len(customers)} updated customers")

            # Process updates (insert/update to your database)
            for row in customers.iter_rows(named=True):
                print(f"  Updated: {row['No']} - {row['Name']}")

            # Save to staging
            customers.write_parquet(f"updates_{datetime.now():%Y%m%d_%H%M%S}.parquet")
        else:
            print("No updates found")

        # Update sync state
        state["last_sync"] = datetime.now(timezone.utc).isoformat()
        save_state(state)

asyncio.run(main())
```

### Example 4: Batch Fetch with Related Data

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth
from odyn.query import F

async def get_customer_with_invoices(client, customer_nos):
    """Fetch customers and their recent invoices in parallel."""

    # Fetch customers and invoices concurrently
    customers, invoices = await asyncio.gather(
        client.get_batch(
            "customers",
            "No",
            customer_nos,
            select=["No", "Name", "Balance_LCY"],
        ),
        client.get_batch(
            "salesInvoices",
            "Sell_to_Customer_No",
            customer_nos,
            select=["No", "Sell_to_Customer_No", "Amount", "Posting_Date"],
        ),
    )

    return customers, invoices

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("user", "pass"),
    ) as client:
        # Get list of top customers
        top_customers_query = (
            ODataQuery()
            .select("No")
            .filter(F.Balance_LCY > 10000)
            .top(100)
        )
        top_df = await client.get("customers", query=top_customers_query)
        customer_nos = top_df["No"].to_list()

        # Fetch full details + invoices
        customers, invoices = await get_customer_with_invoices(client, customer_nos)

        print(f"Fetched {len(customers)} customers with {len(invoices)} invoices")

        # Join data
        import polars as pl
        joined = customers.join(
            invoices.group_by("Sell_to_Customer_No").agg(
                pl.col("Amount").sum().alias("total_invoiced"),
                pl.len().alias("invoice_count"),
            ),
            left_on="No",
            right_on="Sell_to_Customer_No",
            how="left",
        )

        print(joined.head(10))

asyncio.run(main())
```

### Example 5: Streaming Large Dataset to Parquet Files

```python
import asyncio
from pathlib import Path
from odyn import BCWebServiceClient, BasicAuth

async def export_large_dataset(client, endpoint, output_dir):
    """Stream large dataset to multiple Parquet files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    page_num = 0
    total_rows = 0

    async for page_df in client.get_stream(endpoint):
        output_file = output_dir / f"{endpoint}_{page_num:04d}.parquet"
        page_df.write_parquet(output_file)

        page_num += 1
        total_rows += len(page_df)
        print(f"Wrote {output_file.name}: {len(page_df)} rows (total: {total_rows})")

    print(f"Export complete: {total_rows} rows in {page_num} files")

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("user", "pass"),
        max_pages=1000,  # Allow many pages
    ) as client:
        await export_large_dataset(client, "itemLedgerEntries", "./exports/item_ledger")
        await export_large_dataset(client, "generalLedgerEntries", "./exports/gl_entries")

asyncio.run(main())
```

### Example 6: Sync Client in Django View

```python
# views.py
from django.http import JsonResponse
from odyn import BCWebServiceClientSync, BasicAuth
from odyn.query import ODataQuery, F

# Create client once (reuse across requests)
bc_client = BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
    cache_dir="/tmp/odyn_cache",
    cache_ttl=300,  # 5 minute cache
)

def customer_list(request):
    """API endpoint to list customers."""
    # Get query parameters
    min_balance = float(request.GET.get("min_balance", 0))
    limit = int(request.GET.get("limit", 100))

    # Build query
    query = (
        ODataQuery()
        .select("No", "Name", "Balance_LCY", "City")
        .filter(F.Balance_LCY >= min_balance)
        .order_by("Name")
        .top(limit)
    )

    # Fetch from BC (blocking call)
    customers = bc_client.get("customers", query=query)

    # Return as JSON
    return JsonResponse({
        "count": len(customers),
        "customers": customers.to_dicts(),
    })

def customer_detail(request, customer_no):
    """API endpoint for single customer."""
    try:
        customer = bc_client.get_by_key("customers", customer_no)
        return JsonResponse(customer)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=404)
```

### Example 7: Complete ETL Pipeline

```python
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from odyn import BCWebServiceClient, BasicAuth
from odyn.query import ODataQuery, F

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BCDataPipeline:
    def __init__(self, server, instance, auth, output_dir):
        self.server = server
        self.instance = instance
        self.auth = auth
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run(self):
        """Execute the full ETL pipeline."""
        logger.info("Starting BC data pipeline")

        async with BCWebServiceClient.create(
            server=self.server,
            instance=self.instance,
            auth=self.auth,
            cache_dir=self.output_dir / ".cache",
            cache_ttl=3600,
            requests_per_minute=300.0,
            on_response=self._log_response,
        ) as client:
            # Extract
            logger.info("Extracting data from BC...")
            customers = await self._extract_customers(client)
            invoices = await self._extract_invoices(client)

            # Transform
            logger.info("Transforming data...")
            customer_summary = self._transform_customer_summary(customers, invoices)

            # Load
            logger.info("Loading data to output...")
            await self._load(customers, invoices, customer_summary)

        logger.info("Pipeline complete")

    def _log_response(self, *, method, url, status_code, duration_ms):
        logger.debug(f"{method} {url} -> {status_code} ({duration_ms:.0f}ms)")

    async def _extract_customers(self, client):
        query = ODataQuery().select(
            "No", "Name", "Balance_LCY", "Credit_Limit_LCY",
            "City", "Country_Region_Code", "SystemModifiedAt"
        )
        return await client.get("customers", query=query)

    async def _extract_invoices(self, client):
        # Last 90 days of invoices
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

        query = ODataQuery().select(
            "No", "Sell_to_Customer_No", "Amount", "Posting_Date"
        )
        return await client.get_since("salesInvoices", since, query=query)

    def _transform_customer_summary(self, customers, invoices):
        import polars as pl

        # Aggregate invoices by customer
        invoice_summary = invoices.group_by("Sell_to_Customer_No").agg(
            pl.col("Amount").sum().alias("total_invoiced_90d"),
            pl.len().alias("invoice_count_90d"),
        )

        # Join with customers
        return customers.join(
            invoice_summary,
            left_on="No",
            right_on="Sell_to_Customer_No",
            how="left",
        ).with_columns(
            pl.col("total_invoiced_90d").fill_null(0),
            pl.col("invoice_count_90d").fill_null(0),
        )

    async def _load(self, customers, invoices, customer_summary):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        customers.write_parquet(self.output_dir / f"customers_{timestamp}.parquet")
        invoices.write_parquet(self.output_dir / f"invoices_{timestamp}.parquet")
        customer_summary.write_parquet(self.output_dir / f"customer_summary_{timestamp}.parquet")

        # Also write CSV for business users
        customer_summary.write_csv(self.output_dir / f"customer_summary_{timestamp}.csv")

async def main():
    pipeline = BCDataPipeline(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("DOMAIN\\user", "password"),
        output_dir="./data_exports",
    )
    await pipeline.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting Guide

### Connection Issues

#### "Connection refused" / "Cannot connect"

**Causes:**
- Wrong server URL or port
- BC server not running
- Firewall blocking connection

**Solutions:**
```python
# Verify URL format
server="https://bc-server:7048"  # Include protocol and port

# Check if server is reachable
import httpx
response = httpx.get("https://bc-server:7048", verify=False)
print(response.status_code)
```

#### SSL Certificate Errors

**Causes:**
- Self-signed certificate
- Certificate hostname mismatch
- Expired certificate

**Solutions:**
```python
# For development/internal servers with self-signed certs
client = BCWebServiceClient.create(
    ...,
    verify_ssl=False,  # ONLY for internal/dev environments
)
```

#### Timeout Errors

**Causes:**
- Slow BC server
- Large response
- Network latency

**Solutions:**
```python
# Increase timeout
client = BCWebServiceClient.create(
    ...,
    timeout=120.0,  # 2 minutes
)

# Or use streaming for large datasets
async for page in client.get_stream("largeEndpoint"):
    process(page)
```

### Authentication Issues

#### 401 Unauthorized

**Causes:**
- Wrong username/password
- Missing domain prefix
- Need Web Service Access Key instead of Windows password

**Solutions:**
```python
# Include domain
auth = BasicAuth("DOMAIN\\username", "password")

# Try Web Service Access Key
# (Find in BC: Users > Web Service Access Key)
auth = BasicAuth("username", "web_service_access_key")
```

#### 403 Forbidden

**Causes:**
- User lacks permissions to the endpoint
- Endpoint not published
- License issue

**Solutions:**
- Check BC permissions for the user
- Verify endpoint is Published in Web Services page
- Check BC license includes OData access

### Query Issues

#### 400 Bad Request

**Causes:**
- Invalid filter syntax
- Non-existent field name
- Invalid value type

**Solutions:**
```python
# Check field name exactly matches OData
# (Spaces become underscores, special chars removed)
F.Balance_LCY  # Not F.Balance (LCY) or F.BalanceLCY

# Check value types
F.Balance > 1000      # Number, not string
F.Name == "John"      # String with quotes
F.Blocked == False    # Boolean, not "False"
```

#### 404 Not Found

**Causes:**
- Endpoint doesn't exist
- Wrong endpoint name (case-sensitive)
- Company doesn't exist

**Solutions:**
```python
# List available endpoints
endpoints = await client.get_endpoints()
print(endpoints)

# Check exact name in BC Web Services page
# Use exactly as shown in "Service Name" column
```

#### 414 URI Too Long

**Causes:**
- Filter expression too long (too many OR conditions)

**Solutions:**
```python
# Use get_batch() instead of is_in() for large lists
# DON'T:
query = ODataQuery().filter(F.No.is_in(huge_list))  # URL too long

# DO:
df = await client.get_batch("customers", "No", huge_list)
```

### Performance Issues

#### Slow Queries

**Solutions:**
```python
# 1. Select only needed fields
query = ODataQuery().select("No", "Name")  # Not all fields

# 2. Filter server-side
query = ODataQuery().filter(F.Balance > 0)  # Not client-side

# 3. Use caching for static data
client = BCWebServiceClient.create(..., cache_dir="./cache", cache_ttl=3600)

# 4. Reduce concurrency if BC is overloaded
client = BCWebServiceClient.create(..., max_connections=2)
```

#### Rate Limiting (429 Too Many Requests)

**Solutions:**
```python
# Lower rate limit
client = BCWebServiceClient.create(
    ...,
    requests_per_minute=120.0,  # Lower from default 550
    max_connections=2,          # Lower from default 4
)
```

#### Memory Issues with Large Datasets

**Solutions:**
```python
# Use streaming
async for page in client.get_stream("largeEndpoint"):
    # Process and discard each page
    page.write_parquet(f"page_{i}.parquet")

# Or increase max_pages if you need all data
client = BCWebServiceClient.create(..., max_pages=1000)
```

### Data Issues

#### Empty Results

**Causes:**
- Filter too restrictive
- Wrong company
- Data doesn't exist

**Solutions:**
```python
# Test without filter first
df = await client.get("customers")
print(len(df))  # Check if any data exists

# Check company
client = BCWebServiceClient.create(..., company="CRONUS International Ltd.")
# Company name must match exactly
```

#### Missing Fields

**Causes:**
- Field not included in web service
- Field name different than expected

**Solutions:**
```python
# Fetch without select to see all fields
df = await client.get("customers")
print(df.columns)  # See actual field names

# Check BC page design for included fields
```

#### Wrong Data Types

**Causes:**
- OData returns strings for some fields

**Solutions:**
```python
import polars as pl

# Cast after fetching
df = df.with_columns(
    pl.col("Balance").cast(pl.Float64),
    pl.col("Quantity").cast(pl.Int32),
)
```

---

## API Reference Tables

### Client Methods Summary

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get(endpoint, *, query, paginate, use_cache, on_progress)` | endpoint: str | DataFrame | Fetch with auto-pagination |
| `get_stream(endpoint, *, query, on_progress)` | endpoint: str | AsyncIterator[DataFrame] | Stream pages |
| `get_by_key(endpoint, key, *, select)` | endpoint: str, key: str | dict | Fetch by primary key |
| `get_by_id(endpoint, system_id, *, select)` | endpoint: str, system_id: str | dict | Fetch by SystemId |
| `count(endpoint, *, query)` | endpoint: str | int | Get record count |
| `get_first(endpoint, *, query)` | endpoint: str | dict \| None | Get first match |
| `exists(endpoint, key)` | endpoint: str, key: str | bool | Check existence |
| `get_all(endpoint, *, batch_size)` | endpoint: str | DataFrame | Optimized full fetch |
| `get_batch(endpoint, field, values, *, ...)` | endpoint: str, field: str, values: list | DataFrame | Batch fetch |
| `get_since(endpoint, timestamp, *, ...)` | endpoint: str, timestamp: str | DataFrame | Delta sync (after) |
| `get_before(endpoint, timestamp, *, ...)` | endpoint: str, timestamp: str | DataFrame | Delta sync (before) |
| `get_endpoints()` | - | list[str] | List endpoints |
| `close()` | - | None | Close client |
| `clear_cache()` | - | int | Clear all cache |
| `cleanup_cache()` | - | int | Remove expired entries |

### Client Properties

| Property | Type | Description |
|----------|------|-------------|
| `cache_size` | int | Number of cached entries |
| `cache_stats` | dict \| None | Cache statistics (hits, misses, disk_bytes) |

### ODataQuery Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `select(*fields)` | fields: str... | Self | Select fields |
| `filter(expression)` | expression: FilterExpression | Self | Add filter (ANDed) |
| `filter_raw(odata_str)` | odata_str: str | Self | Add raw filter |
| `expand(*relations)` | relations: str... | Self | Expand relations |
| `order_by(*fields)` | fields: str... | Self | Set sort order |
| `top(n)` | n: int | Self | Limit results |
| `skip(n)` | n: int | Self | Skip first n |
| `count(include)` | include: bool | Self | Include count |
| `build()` | - | dict[str, str] | Generate params |

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

### Exceptions

| Exception | HTTP Code | Description |
|-----------|-----------|-------------|
| `OdynError` | - | Base exception |
| `OdynConnectionError` | - | Network error |
| `OdynTimeoutError` | - | Request timeout |
| `OdynSSLError` | - | SSL error |
| `WebServiceError` | Any | BC HTTP error |
| `AuthenticationError` | 401 | Invalid credentials |
| `ForbiddenError` | 403 | Permission denied |
| `NotFoundError` | 404 | Record not found |
| `ValidationError` | 400 | Invalid request |
| `RateLimitError` | 429 | Too many requests |
| `ServerError` | 5xx | Server error |
| `RetryExhaustedError` | - | All retries failed |
| `QueryValidationError` | - | Invalid query |

### Callback Protocols

**ProgressCallback:**
```python
def callback(*, page: int, records_on_page: int, total_records: int, is_final: bool) -> None
```

**BatchProgressCallback:**
```python
def callback(*, batch: int, total_batches: int, successful: int, failed: int, is_final: bool) -> None
```

**RequestHook:**
```python
def callback(*, method: str, url: str, params: dict[str, str] | None) -> None
```

**ResponseHook:**
```python
def callback(*, method: str, url: str, status_code: int, duration_ms: float) -> None
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.4.0 | 2026-01-16 | Renamed `rate_limit` to `requests_per_minute`, added `max_burst`, cache stats, progress callbacks, hooks, delta sync, sync client |
| 0.3.0 | 2026-01-09 | Replaced custom rate limiting with aiolimiter |
| 0.2.0 | 2026-01-09 | Initial release |

---

*This document is designed to be self-contained. An LLM with access to this document should be able to answer any question about using Odyn, troubleshoot issues, and write correct code without needing additional reference materials.*
