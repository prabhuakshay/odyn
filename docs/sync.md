# Sync Client

`BCWebServiceClientSync` is a synchronous wrapper around the async `BCWebServiceClient`. It runs async operations in a background thread with its own event loop, providing a blocking interface for non-async contexts.

## When to Use

- Scripts and CLI tools that don't use `asyncio`
- Jupyter notebooks
- Django views, Flask routes, and other sync web frameworks
- Any context where `await` is not available

## Creating a Sync Client

```python
from odyn import BCWebServiceClientSync, BasicAuth

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    company="CRONUS International Ltd.",
) as client:
    df = client.get("customers")
    print(df)
```

### Factory Method

`BCWebServiceClientSync.create()` accepts the exact same parameters as `BCWebServiceClient.create()`:

```python
BCWebServiceClientSync.create(
    server: str,
    instance: str,
    auth: AuthStrategy,
    *,
    company: str | None = None,
    timeout: float = 30.0,
    max_pages: int = 100,
    verify_ssl: bool = True,
    cache_dir: Path | str | None = None,
    cache_ttl: int | None = None,
    log_level: int = logging.INFO,
    max_retries: int = 3,
    retry_backoff: float = 1.0,
    max_connections: int = 4,
    requests_per_minute: float | None = 550.0,
    max_burst: int | None = None,
    on_request: RequestHook | None = None,
    on_response: ResponseHook | None = None,
) -> BCWebServiceClientSync
```

See [Client](client.md) for parameter descriptions.

## API

Every method on `BCWebServiceClientSync` mirrors the async client, but blocks instead of returning a coroutine.

### Data Fetching

| Method | Returns | Description |
|--------|---------|-------------|
| `get(endpoint, *, query, paginate, use_cache, on_progress)` | `pl.DataFrame` | Fetch data with pagination and caching |
| `get_by_key(endpoint, key, *, select)` | `dict[str, Any]` | Single record by primary key |
| `get_by_id(endpoint, system_id, *, select)` | `dict[str, Any]` | Single record by SystemId GUID |
| `count(endpoint, *, query)` | `int` | Record count |
| `get_endpoints()` | `list[str]` | Available web service endpoints |

### Helpers

| Method | Returns | Description |
|--------|---------|-------------|
| `get_first(endpoint, *, query)` | `dict \| None` | First matching record |
| `exists(endpoint, key)` | `bool` | Check record existence |
| `get_since(endpoint, timestamp, *, query, use_cache, on_progress)` | `pl.DataFrame` | Records modified after timestamp |
| `get_before(endpoint, timestamp, *, query, use_cache, on_progress)` | `pl.DataFrame` | Records modified before timestamp |
| `get_all(endpoint, *, batch_size)` | `pl.DataFrame` | All records with batching |
| `get_batch(endpoint, field, values, *, ...)` | `pl.DataFrame` | Concurrent batch lookups |

### Cache

| Method/Property | Returns | Description |
|--------|---------|-------------|
| `clear_cache()` | `int` | Remove all cache entries |
| `cleanup_cache()` | `int` | Remove expired entries |
| `cache_size` | `int` | Number of entries (property) |
| `cache_stats` | `dict \| None` | Hit/miss/disk stats (property) |

### Lifecycle

| Method | Description |
|--------|-------------|
| `close()` | Close HTTP client, stop background loop, join thread |
| `__enter__()` / `__exit__()` | Context manager support |

## Examples

### Basic Query

```python
from odyn import BCWebServiceClientSync, BasicAuth
from odyn.query import ODataQuery, F

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    company="CRONUS",
) as client:
    query = ODataQuery().filter(F.Balance_LCY > 1000).top(50)
    df = client.get("customers", query=query)
    print(df)
```

### With Caching

```python
client = BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    cache_dir="~/.cache/odyn",
    cache_ttl=3600,
)

try:
    df = client.get("customers")         # miss
    df = client.get("customers")         # hit
    print(client.cache_stats)
finally:
    client.close()
```

### Batch Operations

```python
with BCWebServiceClientSync.create(...) as client:
    ids = ["C001", "C002", "C003", "C004", "C005"]
    df = client.get_batch(
        "customers",
        field="No",
        values=ids,
        select=["No", "Name", "Balance_LCY"],
    )
```

## How It Works

Internally, `BCWebServiceClientSync`:

1. Creates a standard `BCWebServiceClient` via the async factory
2. Starts a background `threading.Thread` running an `asyncio` event loop
3. Each sync method call submits the async coroutine to the background loop via `asyncio.run_coroutine_threadsafe()`
4. Blocks on `future.result()` until the coroutine completes
5. `close()` stops the background loop and joins the thread

The background thread is a daemon thread — it won't prevent process exit.

## Note on `get_stream()`

`get_stream()` is not available on the sync client because it returns an `AsyncIterator`. Use `get()` with pagination, or `get_all()` instead.
