# Client

`BCWebServiceClient` is the main entry point for interacting with Business Central Web Services. It handles HTTP requests, authentication, pagination, caching, retry logic, rate limiting, and concurrency control.

## Creating a Client

Always use the `create()` factory method. It builds the OData URL from server + instance and optionally sets up caching.

```python
from odyn import BCWebServiceClient, BasicAuth

async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    company="CRONUS International Ltd.",
) as client:
    df = await client.get("customers")
```

### Factory Method Parameters

```python
BCWebServiceClient.create(
    server: str,                              # Required. Server URL (e.g., "https://bc-server:7048")
    instance: str,                            # Required. BC instance name (e.g., "BC210")
    auth: AuthStrategy,                       # Required. BasicAuth or APIKeyAuth

    # Scoping
    company: str | None = None,               # Company name. Adds Company('...') to URLs.

    # Timeouts & pagination
    timeout: float = 30.0,                    # HTTP timeout in seconds
    max_pages: int = 100,                     # Max pages to auto-paginate

    # SSL
    verify_ssl: bool = True,                  # Set False for self-signed certs

    # Caching
    cache_dir: Path | str | None = None,      # Enable Parquet cache at this directory
    cache_ttl: int | None = None,             # Cache TTL in seconds (None = never expire)

    # Logging
    log_level: int = logging.INFO,            # Python logging level

    # Retry
    max_retries: int = 3,                     # Retry attempts for transient errors
    retry_backoff: float = 1.0,               # Base delay for exponential backoff

    # Concurrency & rate limiting
    max_connections: int = 4,                  # Max concurrent HTTP connections
    requests_per_minute: float | None = 550.0, # Rate limit (None = disabled)
    max_burst: int | None = None,             # Burst size (defaults to max_connections)

    # Hooks
    on_request: RequestHook | None = None,     # Called before each HTTP request
    on_response: ResponseHook | None = None,   # Called after each HTTP response
)
```

### URL Construction

The factory builds the base URL as `{server}/{instance}/ODataV4`. When `company` is set, endpoint URLs become:

```
{server}/{instance}/ODataV4/Company('{company}')/{endpoint}
```

## Core Methods

### `get()` — Fetch data as a DataFrame

```python
async def get(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
    paginate: bool = True,
    use_cache: bool = True,
    on_progress: ProgressCallback | None = None,
) -> pl.DataFrame
```

The primary method. Fetches data from an endpoint, handles pagination, caching, and returns a Polars DataFrame.

```python
# All customers
df = await client.get("customers")

# With a query
from odyn.query import ODataQuery, F
query = ODataQuery().filter(F.Balance_LCY > 1000).top(50)
df = await client.get("customers", query=query)

# Skip cache
df = await client.get("customers", use_cache=False)

# Single page only
df = await client.get("customers", paginate=False)
```

**Pagination:** When `paginate=True` (default), Odyn follows `@odata.nextLink` up to `max_pages` pages. All pages are concatenated into a single DataFrame using `pl.concat(..., how="diagonal_relaxed")`.

**Caching:** When a `cache_dir` is configured and `use_cache=True`, results are cached as Parquet files. Cache hits return instantly without an HTTP request. Empty results are not cached.

### `get_stream()` — Stream pages as DataFrames

```python
async def get_stream(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
    on_progress: ProgressCallback | None = None,
) -> AsyncIterator[pl.DataFrame]
```

Yields each page as a separate DataFrame. Use this for large datasets where you don't want everything in memory at once.

```python
async for page in client.get_stream("largeDataset"):
    process(page)
```

Streaming bypasses caching.

### `get_by_key()` — Fetch a single record by primary key

```python
async def get_by_key(
    endpoint: str,
    key: str,
    *,
    select: list[str] | None = None,
) -> dict[str, Any]
```

Returns a dictionary for a single record.

```python
customer = await client.get_by_key("customers", "C00010")
print(customer["Name"])

# Select specific fields
customer = await client.get_by_key("customers", "C00010", select=["No", "Name"])
```

### `get_by_id()` — Fetch by SystemId (GUID)

```python
async def get_by_id(
    endpoint: str,
    system_id: str,
    *,
    select: list[str] | None = None,
) -> dict[str, Any]
```

```python
customer = await client.get_by_id("customers", "12345678-1234-1234-1234-123456789012")
```

### `count()` — Get record count

```python
async def count(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
) -> int
```

Only `$filter` from the query is sent to `/$count`.

```python
total = await client.count("customers")
active = await client.count("customers", query=ODataQuery().filter(F.Status == "Active"))
```

### `get_endpoints()` — List available endpoints

```python
async def get_endpoints() -> list[str]
```

Queries the OData service document to discover published web services.

```python
endpoints = await client.get_endpoints()
# ['customers', 'vendors', 'items', 'salesOrders', ...]
```

## Helper Methods

### `get_first()` — First matching record

```python
async def get_first(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
) -> dict[str, Any] | None
```

Returns the first record matching the query, or `None`.

```python
customer = await client.get_first("customers", query=ODataQuery().filter(F.Name == "John"))
```

### `exists()` — Check if a record exists

```python
async def exists(endpoint: str, key: str) -> bool
```

```python
if await client.exists("customers", "C00010"):
    print("Customer exists")
```

### `get_since()` — Records modified after a timestamp

```python
async def get_since(
    endpoint: str,
    timestamp: str,
    *,
    query: ODataQuery | None = None,
    use_cache: bool = False,
    on_progress: ProgressCallback | None = None,
) -> pl.DataFrame
```

Adds `SystemModifiedAt gt {timestamp}` to the filter. Defaults to `use_cache=False` since you typically want fresh data for delta syncs.

```python
from datetime import datetime, timedelta, timezone
since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
updated = await client.get_since("customers", since)
```

### `get_before()` — Records modified before a timestamp

```python
async def get_before(
    endpoint: str,
    timestamp: str,
    *,
    query: ODataQuery | None = None,
    use_cache: bool = True,
    on_progress: ProgressCallback | None = None,
) -> pl.DataFrame
```

Adds `SystemModifiedAt lt {timestamp}` to the filter.

```python
before = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
stale = await client.get_before("customers", before)
```

### `get_all()` — Fetch all records

```python
async def get_all(
    endpoint: str,
    *,
    batch_size: int = 1000,
) -> pl.DataFrame
```

Fetches all records with `$top={batch_size}` for optimized page sizes.

```python
all_customers = await client.get_all("customers")
```

### `get_batch()` — Concurrent batch lookups

```python
async def get_batch(
    endpoint: str,
    field: str,
    values: list[Any],
    *,
    batch_size: int = 50,
    select: list[str] | None = None,
    expand: list[str] | None = None,
    order_by: list[str] | None = None,
    additional_filter: FilterExpression | None = None,
    fail_fast: bool = False,
    use_cache: bool = True,
    on_progress: BatchProgressCallback | None = None,
) -> pl.DataFrame
```

Chunks `values` into batches, creates `is_in()` filters, and runs all batches concurrently (controlled by `max_connections` and `requests_per_minute`).

```python
customer_ids = ["C001", "C002", ..., "C500"]
df = await client.get_batch(
    "customers",
    field="No",
    values=customer_ids,
    batch_size=50,
    select=["No", "Name", "Balance_LCY"],
)
```

See [Advanced](advanced.md) for batch progress callbacks and error handling.

## Cache Management

These methods are available on the client when caching is enabled:

| Method | Returns | Description |
|--------|---------|-------------|
| `clear_cache()` | `int` | Remove all cache entries. Returns count. |
| `cleanup_cache()` | `int` | Remove expired entries. Returns count. |
| `cache_size` | `int` | Number of cached entries (property). |
| `cache_stats` | `dict[str, int] \| None` | `{"hits": N, "misses": N, "disk_bytes": N}` or `None` if no cache. |

## Lifecycle

Use the client as an async context manager to ensure the HTTP connection pool is closed:

```python
async with BCWebServiceClient.create(...) as client:
    # use client
# HTTP connections are closed here
```

Or close manually:

```python
client = BCWebServiceClient.create(...)
try:
    df = await client.get("customers")
finally:
    await client.close()
```

## Retry Behavior

Odyn retries on:
- **Timeouts** (`TimeoutError`)
- **Connection errors** (`ConnectionError`)
- **Rate limits** (`RateLimitError` / HTTP 429) — respects `Retry-After` header
- **Server errors** (`ServerError` / HTTP 5xx)

Non-retryable (raised immediately):
- `AuthenticationError` (401)
- `ForbiddenError` (403)
- `NotFoundError` (404)
- `ValidationError` (400)
- `SSLError`

Backoff formula: `base_delay * 2^attempt + random_jitter`

After all retries are exhausted, `RetryExhaustedError` is raised with the last exception attached.

## Rate Limiting

Uses a token-bucket algorithm (via `aiolimiter`):

- `requests_per_minute=550.0` — sustained rate (default)
- `max_burst=None` — defaults to `max_connections` to prevent startup hammering
- Set `requests_per_minute=None` to disable

Rate limiting is applied inside the concurrency semaphore to prevent queuing buildup.

## Concurrency

- `max_connections=4` — limits both the httpx connection pool and the asyncio semaphore
- BC on-premises typically handles 4-10 concurrent connections well
- `get_batch()` runs batches concurrently, bounded by these limits
