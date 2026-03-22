# Odyn — Complete LLM Reference

> This is a single-file, self-contained reference for the Odyn Python library. Feed this to an AI assistant and it will know 100% of Odyn's capabilities, every class, every method, every parameter, every type, and every pattern.

## What Odyn Is

Odyn is an async-first Python client for Microsoft Dynamics 365 Business Central **on-premises OData Web Services** (the `/ODataV4` endpoint). It does NOT target the standard BC API v2.0 REST endpoints.

- **Version:** 0.4.2
- **Python:** >= 3.12
- **Dependencies:** httpx >= 0.28, polars >= 1.36, aiolimiter >= 1.2
- **License:** MIT

## Installation

```bash
pip install odyn
# or
uv add odyn
```

---

## Architecture Overview

```
odyn/
├── auth.py         — BasicAuth, APIKeyAuth, AuthStrategy type alias
├── client.py       — BCWebServiceClient (async), protocols (hooks, callbacks)
├── sync.py         — BCWebServiceClientSync (sync wrapper)
├── cache.py        — ParquetCache, CacheMetadata
├── exceptions.py   — Exception hierarchy (OdynError and subclasses)
└── query/
    ├── builder.py      — ODataQuery (fluent query builder)
    ├── fields.py       — F singleton, Field class
    ├── expressions.py  — Comparison, InList, Raw, And, Or, FilterExpression protocol
    └── types.py        — ODataValue type alias, VALID_OPERATORS constant
```

All public APIs are re-exported from `odyn` (top-level) and `odyn.query`.

---

## Authentication

### BasicAuth

```python
from odyn import BasicAuth

auth = BasicAuth(username="DOMAIN\\user", password="password")
auth.auth_header  # "Basic RE9NQUlOXHVzZXI6cGFzc3dvcmQ="
```

- `username: str` — supports `DOMAIN\user` format
- `password: str`
- `auth_header: str` (property) — Base64-encoded `Basic` header value
- `apply(request: httpx.Request) -> httpx.Request` — adds Authorization header
- `__repr__` hides password: `BasicAuth(username='...', password='***')`
- Frozen dataclass with `__slots__`

### APIKeyAuth

```python
from odyn import APIKeyAuth

# Default: Bearer token in Authorization header
auth = APIKeyAuth(api_key="my-key")
# Header: Authorization: Bearer my-key

# Custom header, no prefix
auth = APIKeyAuth(api_key="my-key", header_name="X-API-Key", prefix="")
# Header: X-API-Key: my-key
```

- `api_key: str`
- `header_name: str = "Authorization"`
- `prefix: str = "Bearer"` — set `""` for no prefix
- `auth_header: str` (property) — `"{prefix} {api_key}"` or just `"{api_key}"`
- `apply(request: httpx.Request) -> httpx.Request`
- `__repr__` hides key: `APIKeyAuth(api_key='***', header_name='...')`
- Frozen dataclass with `__slots__`

### AuthStrategy

```python
AuthStrategy = BasicAuth | APIKeyAuth
```

---

## Client — BCWebServiceClient

### Creating a Client

```python
from odyn import BCWebServiceClient, BasicAuth

async with BCWebServiceClient.create(
    server="https://bc-server:7048",     # required
    instance="BC210",                     # required
    auth=BasicAuth("user", "pass"),       # required (BasicAuth or APIKeyAuth)
    company="CRONUS International Ltd.",  # optional — scopes all requests
    timeout=30.0,                         # HTTP timeout seconds (default: 30)
    max_pages=100,                        # max pagination pages (default: 100)
    verify_ssl=True,                      # set False for self-signed certs
    cache_dir="~/.cache/odyn",            # enable Parquet cache
    cache_ttl=3600,                       # cache TTL seconds (None = never expire)
    log_level=logging.INFO,               # logging level
    max_retries=3,                        # retry attempts (default: 3)
    retry_backoff=1.0,                    # base backoff seconds (default: 1.0)
    max_connections=4,                    # concurrent connections (default: 4)
    requests_per_minute=550.0,            # rate limit (None = disabled)
    max_burst=None,                       # burst size (defaults to max_connections)
    on_request=None,                      # RequestHook callback
    on_response=None,                     # ResponseHook callback
) as client:
    df = await client.get("customers")
```

URL built as: `{server}/{instance}/ODataV4`
With company: `{server}/{instance}/ODataV4/Company('{company}')/{endpoint}`

### Core Methods

#### get() → pl.DataFrame

```python
df = await client.get(
    "customers",                    # endpoint name
    query=ODataQuery(),             # optional query
    paginate=True,                  # auto-paginate (default: True)
    use_cache=True,                 # use cache (default: True)
    on_progress=callback,           # ProgressCallback
)
```

Auto-paginates following `@odata.nextLink`. Caches non-empty results as Parquet.

#### get_stream() → AsyncIterator[pl.DataFrame]

```python
async for page in client.get_stream("largeDataset", query=query, on_progress=callback):
    process(page)
```

Yields each page as a separate DataFrame. No caching.

#### get_by_key() → dict[str, Any]

```python
record = await client.get_by_key("customers", "C00010", select=["No", "Name"])
```

URL: `endpoint('{key}')`

#### get_by_id() → dict[str, Any]

```python
record = await client.get_by_id("customers", "12345678-...", select=["No", "Name"])
```

URL: `endpoint({system_id})` — no quotes (GUID format)

#### count() → int

```python
n = await client.count("customers", query=ODataQuery().filter(F.Status == "Active"))
```

Only `$filter` is sent to `/$count`.

#### get_endpoints() → list[str]

```python
endpoints = await client.get_endpoints()
# ['customers', 'vendors', 'items', ...]
```

### Helper Methods

#### get_first() → dict | None

```python
record = await client.get_first("customers", query=ODataQuery().filter(F.Name == "John"))
```

Returns first match or `None`. Uses `top(1)` internally.

#### exists() → bool

```python
if await client.exists("customers", "C00010"):
    ...
```

Catches `NotFoundError` internally.

#### get_since() → pl.DataFrame

```python
updated = await client.get_since("customers", "2024-01-15T10:30:00Z", query=query, use_cache=False)
```

Adds `SystemModifiedAt gt {timestamp}`. Default `use_cache=False`.

#### get_before() → pl.DataFrame

```python
stale = await client.get_before("customers", "2024-01-15T10:30:00Z", query=query, use_cache=True)
```

Adds `SystemModifiedAt lt {timestamp}`. Default `use_cache=True`.

#### get_all() → pl.DataFrame

```python
all_data = await client.get_all("customers", batch_size=1000)
```

Uses `$top={batch_size}` for optimized page sizes.

#### get_batch() → pl.DataFrame

```python
df = await client.get_batch(
    "customers",
    field="No",                              # field to filter on
    values=["C001", "C002", ..., "C500"],    # values to match
    batch_size=50,                           # values per batch (default: 50)
    select=["No", "Name"],                   # optional
    expand=["SalesLines"],                   # optional
    order_by=["Name asc"],                   # optional
    additional_filter=(F.Blocked == False),   # optional extra filter
    fail_fast=False,                         # raise on first error? (default: False)
    use_cache=True,                          # default: True
    on_progress=batch_callback,              # BatchProgressCallback
)
```

Chunks values → `is_in()` filters → concurrent requests → concatenated result.

### Cache Methods

```python
client.clear_cache()    # int: remove all entries
client.cleanup_cache()  # int: remove expired entries
client.cache_size       # int: entry count (property)
client.cache_stats      # dict | None: {"hits", "misses", "disk_bytes"} (property)
```

### Lifecycle

```python
async with BCWebServiceClient.create(...) as client:
    ...  # auto-closes

# Or manually:
client = BCWebServiceClient.create(...)
await client.close()
```

---

## Sync Client — BCWebServiceClientSync

Synchronous wrapper. Runs async ops in a background thread.

```python
from odyn import BCWebServiceClientSync, BasicAuth

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
    company="CRONUS",
    # ... all same params as BCWebServiceClient.create()
) as client:
    df = client.get("customers")
```

**Has all the same methods as BCWebServiceClient** except `get_stream()`:

`get()`, `get_by_key()`, `get_by_id()`, `count()`, `get_endpoints()`, `get_first()`, `exists()`, `get_since()`, `get_before()`, `get_all()`, `get_batch()`, `clear_cache()`, `cleanup_cache()`, `cache_size`, `cache_stats`, `close()`

All methods block and return directly (no `await`).

---

## Query Builder

### ODataQuery

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY")     # $select
    .filter(F.Balance_LCY > 1000)             # $filter (AND'd with other filters)
    .filter(F.Status == "Active")             # multiple filters = AND
    .filter_raw("contains(Name, 'Corp')")     # raw OData string (escape hatch)
    .expand("SalesLines")                     # $expand
    .order_by("Name asc", "Balance desc")     # $orderby
    .top(100)                                 # $top
    .skip(50)                                 # $skip
    .count()                                  # $count=true
)

params = query.build()  # dict[str, str]
```

### F Singleton

Creates `Field` objects via attribute access:

```python
F.Name         # Field("Name")
F.Balance_LCY  # Field("Balance_LCY")
```

Field names must: start with letter/underscore, contain only alphanumerics/underscores.

### Field Operators → Comparison

```python
F.Status == "Active"     # Comparison("Status", "eq", "Active")
F.Status != "Inactive"   # Comparison("Status", "ne", "Inactive")
F.Balance > 1000         # Comparison("Balance", "gt", 1000)
F.Balance >= 0           # Comparison("Balance", "ge", 0)
F.Balance < 500          # Comparison("Balance", "lt", 500)
F.Count <= 10            # Comparison("Count", "le", 10)
```

### is_in() → InList

```python
F.Type.is_in(["Sale", "Purchase"])
# InList("Type", ("Sale", "Purchase"))
# OData: "(Type eq 'Sale' or Type eq 'Purchase')"
```

OData has no native IN — this generates OR chains.

### Combining Expressions

```python
# AND with &
expr = (F.Status == "Active") & (F.Balance > 0)
# "(Status eq 'Active' and Balance gt 0)"

# OR with |
expr = (F.City == "London") | (F.City == "Berlin")
# "(City eq 'London' or City eq 'Berlin')"

# Chaining flattens
expr = (F.A == 1) & (F.B == 2) & (F.C == 3)
# "(A eq 1 and B eq 2 and C eq 3)"

# Mixed
expr = ((F.City == "London") | (F.City == "Berlin")) & (F.Balance > 1000)
# "((City eq 'London' or City eq 'Berlin') and Balance gt 1000)"
```

### Raw Expressions

```python
from odyn.query.expressions import Raw

Raw("contains(Name, 'Corp')")
Raw("startswith(Email, 'admin')")

# Via builder
ODataQuery().filter_raw("contains(Name, 'Corp')")
```

### ODataValue Types

```python
type ODataValue = str | int | float | bool | None | date | datetime
```

| Python | OData | Example |
|--------|-------|---------|
| `str` | `'value'` | `F.Name == "O'Brien"` → `Name eq 'O''Brien'` |
| `int` | `123` | `F.Count == 5` → `Count eq 5` |
| `float` | `1.5` | `F.Rate == 1.5` → `Rate eq 1.5` |
| `bool` | `true`/`false` | `F.Active == True` → `Active eq true` |
| `None` | `null` | `F.Code == None` → `Code eq null` |
| `date` | `2024-01-15` | ISO format |
| `datetime` | `2024-01-15T10:30:00Z` | ISO format with Z suffix |

### Valid Operators

```python
VALID_OPERATORS = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})
```

### FilterExpression Protocol

Any object with `to_odata() -> str` works. Runtime-checkable.

```python
@runtime_checkable
class FilterExpression(Protocol):
    def to_odata(self) -> str: ...
```

### Expression Classes Summary

| Class | Attributes | OData output |
|-------|-----------|-------------|
| `Comparison` | `field, operator, value` | `field op value` |
| `InList` | `field, values` | `(field eq v1 or field eq v2)` |
| `Raw` | `expression` | expression as-is |
| `And` | `expressions: tuple[FilterExpression, ...]` | `(expr1 and expr2)` |
| `Or` | `expressions: tuple[FilterExpression, ...]` | `(expr1 or expr2)` |

All support `&` (→ And) and `|` (→ Or). All are frozen dataclasses with `__slots__`.

---

## Caching — ParquetCache

```python
from pathlib import Path
from odyn import ParquetCache

cache = ParquetCache(Path("~/.cache/odyn").expanduser(), default_ttl=3600)
```

### How It Works

Each entry = two files: `{sha256_key}.parquet` + `{sha256_key}.json` (metadata).

Cache keys are 64-char hex SHA256 hashes of URL + sorted params. Parameter order doesn't matter.

### API

```python
key = ParquetCache.make_key(url, params)           # static, SHA256

cache.set(key, df, url=url, params=params, ttl_seconds=3600)  # store
df = cache.get(key)                                 # pl.DataFrame | None
cache.exists(key)                                   # bool (non-expired)
key in cache                                        # same as exists()
cache.delete(key)                                   # bool (True if existed)
cache.clear()                                       # int (entries removed, resets stats)
cache.cleanup()                                     # int (expired entries removed)
cache.size()                                        # int (total entries)
cache.stats()                                       # {"hits": N, "misses": N, "disk_bytes": N}
```

### TTL Behavior

An entry expires if:
- Its stored `ttl_seconds` has elapsed, OR
- The cache's `default_ttl` has elapsed

Changing `default_ttl` takes effect immediately for all existing entries.

### CacheMetadata

```python
from odyn import CacheMetadata

# Stored as JSON alongside each Parquet file
metadata.url           # str
metadata.params        # dict[str, str] | None
metadata.created_at    # float (Unix timestamp)
metadata.ttl_seconds   # int | None
metadata.is_expired    # bool (property)
metadata.age           # float (property, seconds)
```

---

## Exceptions

### Hierarchy

```
OdynError
├── QueryValidationError
├── RetryExhaustedError          (attempts: int, last_exception: Exception)
├── ConnectionError              (url: str | None, original_error: Exception | None)
│   ├── TimeoutError             (timeout: float | None)
│   └── SSLError
└── WebServiceError              (message, status_code, url, response_body, odata_error)
    ├── AuthenticationError      (401)
    ├── ForbiddenError           (403)
    ├── NotFoundError            (404)
    ├── ValidationError          (400)
    ├── RateLimitError           (429, retry_after: float | None)
    └── ServerError              (5xx)
```

### Import Aliases

```python
from odyn import (
    OdynError,
    OdynConnectionError,   # shadows builtin — aliased
    OdynTimeoutError,      # shadows builtin — aliased
    OdynSSLError,          # shadows builtin — aliased
    # ... all others by their class name
)
```

### WebServiceError Attributes

```python
e.message         # str
e.status_code     # int
e.url             # str
e.response_body   # str
e.odata_error     # dict[str, Any]
str(e)            # "[{status_code}] {message}"
```

### Retry Behavior

| Exception | Retried? |
|-----------|----------|
| TimeoutError | Yes |
| ConnectionError | Yes |
| RateLimitError (429) | Yes (respects Retry-After header) |
| ServerError (5xx) | Yes |
| AuthenticationError (401) | No |
| ForbiddenError (403) | No |
| NotFoundError (404) | No |
| ValidationError (400) | No |
| SSLError | No |

Backoff: `retry_backoff * 2^attempt + random_jitter`
After exhaustion: `RetryExhaustedError(attempts=N, last_exception=e)`

---

## Protocols (Callbacks & Hooks)

### ProgressCallback

```python
def on_progress(*, page: int, records_on_page: int, total_records: int, is_final: bool) -> None: ...
```

Used in: `get()`, `get_stream()`, `get_since()`, `get_before()`

### BatchProgressCallback

```python
def on_progress(*, batch: int, total_batches: int, successful: int, failed: int, is_final: bool) -> None: ...
```

Used in: `get_batch()`

### RequestHook

```python
def on_request(*, method: str, url: str, params: dict[str, str] | None) -> None: ...
```

Called before each HTTP request.

### ResponseHook

```python
def on_response(*, method: str, url: str, status_code: int, duration_ms: float) -> None: ...
```

Called after each HTTP response.

All four are `@runtime_checkable Protocol` classes — any callable with matching keyword-only args works.

---

## Concurrency & Rate Limiting

- **max_connections** (default: 4) — httpx pool size + asyncio semaphore
- **requests_per_minute** (default: 550.0) — token-bucket rate limiter (set `None` to disable)
- **max_burst** (default: max_connections) — tokens available immediately before throttling

Rate limiting runs inside the semaphore to prevent queue buildup.

`get_batch()` submits all batches concurrently, bounded by these controls.

---

## Common Patterns

### Async basic usage

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth
from odyn.query import ODataQuery, F

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("user", "pass"),
        company="CRONUS",
    ) as client:
        df = await client.get("customers")
        query = ODataQuery().filter(F.Balance_LCY > 1000).top(50)
        top = await client.get("customers", query=query)

asyncio.run(main())
```

### Sync basic usage

```python
from odyn import BCWebServiceClientSync, BasicAuth

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
) as client:
    df = client.get("customers")
```

### Delta sync

```python
from datetime import datetime, timedelta, timezone
since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
updated = await client.get_since("customers", since)
```

### Batch lookup

```python
df = await client.get_batch(
    "customers", field="No", values=["C001", "C002", "C003"],
    batch_size=50, select=["No", "Name"],
)
```

### Streaming large datasets

```python
async for page in client.get_stream("largeDataset"):
    save(page)
```

### Caching with TTL

```python
client = BCWebServiceClient.create(..., cache_dir="~/.cache/odyn", cache_ttl=3600)
df = await client.get("customers")  # miss
df = await client.get("customers")  # hit
```

### Error handling

```python
from odyn import AuthenticationError, NotFoundError, RetryExhaustedError, OdynError

try:
    df = await client.get("customers")
except AuthenticationError:
    print("Bad credentials")
except NotFoundError:
    print("Endpoint not found")
except RetryExhaustedError as e:
    print(f"Failed after {e.attempts} retries: {e.last_exception}")
except OdynError as e:
    print(f"Odyn error: {e}")
```

### Hooks for observability

```python
def on_request(*, method, url, params):
    print(f">>> {method} {url}")

def on_response(*, method, url, status_code, duration_ms):
    print(f"<<< {status_code} ({duration_ms:.0f}ms)")

client = BCWebServiceClient.create(..., on_request=on_request, on_response=on_response)
```

### OData functions via filter_raw

```python
query = (
    ODataQuery()
    .filter_raw("contains(Name, 'Corp')")
    .filter_raw("startswith(Email, 'sales')")
    .filter(F.Balance > 0)  # mix typed and raw
)
```

### Custom FilterExpression

```python
class ContainsFilter:
    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
    def to_odata(self) -> str:
        return f"contains({self.field}, '{self.value}')"

query = ODataQuery().filter(ContainsFilter("Name", "Corp"))
```

---

## BC-Specific Notes

- OData endpoint: `{server}/{instance}/ODataV4`
- Company scoping: `Company('{name}')` in URL path
- Web services must be published in BC under Administration > Web Services
- Field names: spaces become underscores (e.g., "Balance (LCY)" → `Balance_LCY`)
- Primary key lookup: `endpoint('{key}')` (single-quoted)
- SystemId lookup: `endpoint({guid})` (no quotes)
- `$count` only respects `$filter`
- Pagination via `@odata.nextLink`
- Default OData port: 7048
- Typical concurrent connection limit: 4-10
