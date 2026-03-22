# API Reference

Complete reference for every public class, method, parameter, type, and constant in Odyn.

---

## odyn (top-level package)

### Exports

```python
from odyn import (
    # Auth
    APIKeyAuth,
    AuthStrategy,
    BasicAuth,
    # Client
    BCWebServiceClient,
    BCWebServiceClientSync,
    # Cache
    CacheMetadata,
    ParquetCache,
    # Exceptions
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    OdynConnectionError,
    OdynError,
    OdynSSLError,
    OdynTimeoutError,
    QueryValidationError,
    RateLimitError,
    RetryExhaustedError,
    ServerError,
    ValidationError,
    WebServiceError,
)
```

---

## odyn.auth

### BasicAuth

```python
@dataclass(frozen=True, slots=True)
class BasicAuth:
    username: str
    password: str
```

HTTP Basic Authentication for on-premises Business Central.

| Member | Type | Description |
|--------|------|-------------|
| `username` | `str` | Username. Supports `DOMAIN\user`. |
| `password` | `str` | Password. |
| `auth_header` | `str` (property) | `"Basic {base64(user:pass)}"` |
| `apply(request)` | `httpx.Request -> httpx.Request` | Adds Authorization header. |
| `__repr__()` | `str` | `"BasicAuth(username='...', password='***')"` |

### APIKeyAuth

```python
@dataclass(frozen=True, slots=True)
class APIKeyAuth:
    api_key: str
    header_name: str = "X-API-Key"
    prefix: str = ""
```

API Key Authentication.

| Member | Type | Description |
|--------|------|-------------|
| `api_key` | `str` | The API key value. |
| `header_name` | `str` | HTTP header name (default: `"X-API-Key"`). |
| `prefix` | `str` | Value prefix (default: `""`). Set e.g. `"Bearer"` to prepend. |
| `auth_header` | `str` (property) | `"{prefix} {api_key}"` or `"{api_key}"` if prefix is empty. |
| `apply(request)` | `httpx.Request -> httpx.Request` | Adds the auth header. |
| `__repr__()` | `str` | `"APIKeyAuth(api_key='***', header_name='...')"` |

### AuthStrategy

```python
AuthStrategy = BasicAuth | APIKeyAuth
```

Type alias for supported authentication strategies.

---

## odyn.client

### BCWebServiceClient

```python
@dataclass
class BCWebServiceClient:
    base_url: str
    auth: AuthStrategy
    company: str | None = None
    timeout: float = 30.0
    max_pages: int = 100
    verify_ssl: bool = True
    cache: ParquetCache | None = None
    max_retries: int = 3
    retry_backoff: float = 1.0
    max_connections: int = 4
    requests_per_minute: float | None = 550.0
    max_burst: int | None = None
    on_request: RequestHook | None = None
    on_response: ResponseHook | None = None
```

#### create() — class method

```python
@classmethod
def create(
    cls,
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
) -> BCWebServiceClient
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server` | `str` | — | Server URL (e.g., `"https://bc-server:7048"`) |
| `instance` | `str` | — | BC instance name (e.g., `"BC210"`) |
| `auth` | `AuthStrategy` | — | `BasicAuth` or `APIKeyAuth` |
| `company` | `str \| None` | `None` | Company name for URL scoping |
| `timeout` | `float` | `30.0` | HTTP timeout (seconds) |
| `max_pages` | `int` | `100` | Max auto-pagination pages |
| `verify_ssl` | `bool` | `True` | Verify SSL certificates |
| `cache_dir` | `Path \| str \| None` | `None` | Cache directory path |
| `cache_ttl` | `int \| None` | `None` | Cache TTL (seconds) |
| `log_level` | `int` | `logging.INFO` | Logging level |
| `max_retries` | `int` | `3` | Retry attempts for transient errors |
| `retry_backoff` | `float` | `1.0` | Base backoff delay (seconds) |
| `max_connections` | `int` | `4` | Max concurrent connections |
| `requests_per_minute` | `float \| None` | `550.0` | Rate limit (`None` to disable) |
| `max_burst` | `int \| None` | `None` | Burst size (defaults to `max_connections`) |
| `on_request` | `RequestHook \| None` | `None` | Pre-request hook |
| `on_response` | `ResponseHook \| None` | `None` | Post-response hook |

#### get()

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

Fetch data with automatic pagination and caching. Returns Polars DataFrame.

#### get_stream()

```python
async def get_stream(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
    on_progress: ProgressCallback | None = None,
) -> AsyncIterator[pl.DataFrame]
```

Stream pages as individual DataFrames. No caching.

#### get_by_key()

```python
async def get_by_key(
    endpoint: str,
    key: str,
    *,
    select: list[str] | None = None,
) -> dict[str, Any]
```

Fetch single record by primary key. URL: `endpoint('{key}')`.

#### get_by_id()

```python
async def get_by_id(
    endpoint: str,
    system_id: str,
    *,
    select: list[str] | None = None,
) -> dict[str, Any]
```

Fetch single record by SystemId GUID. URL: `endpoint({system_id})`.

#### count()

```python
async def count(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
) -> int
```

Record count. Only `$filter` from the query is used.

#### get_endpoints()

```python
async def get_endpoints() -> list[str]
```

List published web service endpoint names.

#### get_first()

```python
async def get_first(
    endpoint: str,
    *,
    query: ODataQuery | None = None,
) -> dict[str, Any] | None
```

First matching record, or `None`.

#### exists()

```python
async def exists(endpoint: str, key: str) -> bool
```

Check if record exists by primary key.

#### get_since()

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

Records where `SystemModifiedAt > timestamp`.

#### get_before()

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

Records where `SystemModifiedAt < timestamp`.

#### get_all()

```python
async def get_all(
    endpoint: str,
    *,
    batch_size: int = 1000,
) -> pl.DataFrame
```

All records with `$top={batch_size}` for optimized page sizes.

#### get_batch()

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

Concurrent batch lookups. Chunks values, creates `is_in()` filters, runs concurrently.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | — | OData entity set name |
| `field` | `str` | — | Field to filter on |
| `values` | `list[Any]` | — | Values to match (non-empty) |
| `batch_size` | `int` | `50` | Values per batch |
| `select` | `list[str] \| None` | `None` | Fields to return |
| `expand` | `list[str] \| None` | `None` | Relations to include |
| `order_by` | `list[str] \| None` | `None` | Sort clauses |
| `additional_filter` | `FilterExpression \| None` | `None` | Additional filter AND'd with is_in |
| `fail_fast` | `bool` | `False` | Raise on first batch error |
| `use_cache` | `bool` | `True` | Use cache |
| `on_progress` | `BatchProgressCallback \| None` | `None` | Progress callback |

#### Cache Methods

| Member | Signature | Description |
|--------|-----------|-------------|
| `clear_cache()` | `() -> int` | Remove all entries |
| `cleanup_cache()` | `() -> int` | Remove expired entries |
| `cache_size` | `int` (property) | Entry count |
| `cache_stats` | `dict[str, int] \| None` (property) | `{"hits", "misses", "disk_bytes"}` |

#### Lifecycle

| Member | Signature | Description |
|--------|-----------|-------------|
| `close()` | `async () -> None` | Close HTTP client |
| `__aenter__()` | `async () -> Self` | Async context manager enter |
| `__aexit__()` | `async (*args) -> None` | Async context manager exit |

### Protocols

#### ProgressCallback

```python
@runtime_checkable
class ProgressCallback(Protocol):
    def __call__(
        self,
        *,
        page: int,
        records_on_page: int,
        total_records: int,
        is_final: bool,
    ) -> None: ...
```

#### BatchProgressCallback

```python
@runtime_checkable
class BatchProgressCallback(Protocol):
    def __call__(
        self,
        *,
        batch: int,
        total_batches: int,
        successful: int,
        failed: int,
        is_final: bool,
    ) -> None: ...
```

#### RequestHook

```python
@runtime_checkable
class RequestHook(Protocol):
    def __call__(
        self,
        *,
        method: str,
        url: str,
        params: dict[str, str] | None,
    ) -> None: ...
```

#### ResponseHook

```python
@runtime_checkable
class ResponseHook(Protocol):
    def __call__(
        self,
        *,
        method: str,
        url: str,
        status_code: int,
        duration_ms: float,
    ) -> None: ...
```

---

## odyn.sync

### BCWebServiceClientSync

```python
class BCWebServiceClientSync:
    __slots__ = ("_client", "_loop", "_thread")
```

Synchronous wrapper. Runs async operations in a background thread. All methods mirror `BCWebServiceClient` but block.

#### create() — class method

Same signature as `BCWebServiceClient.create()`. Returns `BCWebServiceClientSync`.

#### Methods

All have identical signatures to `BCWebServiceClient` except they return values directly instead of coroutines.

| Method | Returns |
|--------|---------|
| `get(endpoint, *, query, paginate, use_cache, on_progress)` | `pl.DataFrame` |
| `get_by_key(endpoint, key, *, select)` | `dict[str, Any]` |
| `get_by_id(endpoint, system_id, *, select)` | `dict[str, Any]` |
| `count(endpoint, *, query)` | `int` |
| `get_endpoints()` | `list[str]` |
| `get_first(endpoint, *, query)` | `dict[str, Any] \| None` |
| `exists(endpoint, key)` | `bool` |
| `get_since(endpoint, timestamp, *, ...)` | `pl.DataFrame` |
| `get_before(endpoint, timestamp, *, ...)` | `pl.DataFrame` |
| `get_all(endpoint, *, batch_size)` | `pl.DataFrame` |
| `get_batch(endpoint, field, values, *, ...)` | `pl.DataFrame` |
| `clear_cache()` | `int` |
| `cleanup_cache()` | `int` |
| `close()` | `None` |

#### Properties

| Property | Type |
|----------|------|
| `cache_size` | `int` |
| `cache_stats` | `dict[str, int] \| None` |

#### Context Manager

```python
with BCWebServiceClientSync.create(...) as client:
    df = client.get("customers")
```

Note: `get_stream()` is not available on the sync client.

---

## odyn.cache

### ParquetCache

```python
class ParquetCache:
    __slots__ = ("_cache_dir", "_default_ttl", "_hits", "_misses")

    def __init__(self, cache_dir: Path, default_ttl: int | None = None) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache_dir` | `Path` | — | Cache directory (auto-created) |
| `default_ttl` | `int \| None` | `None` | Default TTL in seconds |

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `get` | `(key: str)` | `pl.DataFrame \| None` | Get if valid, else `None` |
| `set` | `(key, df, *, url, params=None, ttl_seconds=None)` | `None` | Store entry |
| `delete` | `(key: str)` | `bool` | Remove entry |
| `exists` | `(key: str)` | `bool` | Check if valid entry exists |
| `clear` | `()` | `int` | Remove all entries |
| `cleanup` | `()` | `int` | Remove expired entries |
| `size` | `()` | `int` | Entry count |
| `stats` | `()` | `dict[str, int]` | `{"hits", "misses", "disk_bytes"}` |
| `make_key` | `(url, params=None)` | `str` | Static. SHA256 hash (64 hex chars) |
| `__contains__` | `(key: str)` | `bool` | `key in cache` support |

### CacheMetadata

```python
@dataclass(slots=True)
class CacheMetadata:
    url: str
    params: dict[str, str] | None
    created_at: float
    ttl_seconds: int | None
```

| Property | Type | Description |
|----------|------|-------------|
| `is_expired` | `bool` | Whether stored TTL has elapsed |
| `age` | `float` | Seconds since creation |

---

## odyn.query

### ODataQuery

```python
@dataclass
class ODataQuery:
    _select: list[str]
    _filters: list[FilterExpression]
    _expand: list[str]
    _order_by: list[str]
    _top: int | None = None
    _skip: int | None = None
    _count: bool = False
```

| Method | Signature | OData param | Description |
|--------|-----------|-------------|-------------|
| `select` | `(*fields: str) -> Self` | `$select` | Fields to return |
| `filter` | `(condition: FilterExpression) -> Self` | `$filter` | Add filter (AND'd) |
| `filter_raw` | `(odata_string: str) -> Self` | `$filter` | Raw OData filter |
| `expand` | `(*relations: str) -> Self` | `$expand` | Related entities |
| `order_by` | `(*fields: str) -> Self` | `$orderby` | Sort order |
| `top` | `(count: int) -> Self` | `$top` | Limit results |
| `skip` | `(count: int) -> Self` | `$skip` | Skip results |
| `count` | `(include: bool = True) -> Self` | `$count` | Include count |
| `build` | `() -> dict[str, str]` | — | Build query params |

### Field

```python
@dataclass(frozen=True, slots=True)
class Field:
    name: str
```

| Operator | OData | Returns |
|----------|-------|---------|
| `==` | `eq` | `Comparison` |
| `!=` | `ne` | `Comparison` |
| `>` | `gt` | `Comparison` |
| `>=` | `ge` | `Comparison` |
| `<` | `lt` | `Comparison` |
| `<=` | `le` | `Comparison` |
| `is_in(values)` | OR chain | `InList` |

### F (singleton)

```python
F: Final[_FieldFactory] = _FieldFactory()
```

Creates `Field` objects via attribute access: `F.Name`, `F.Balance_LCY`, etc.

---

## odyn.query.expressions

### FilterExpression (Protocol)

```python
@runtime_checkable
class FilterExpression(Protocol):
    def to_odata(self) -> str: ...
```

### Comparison

```python
@dataclass(frozen=True, slots=True)
class Comparison:
    field: str
    operator: str    # eq, ne, gt, ge, lt, le
    value: ODataValue
```

| Method | Returns |
|--------|---------|
| `to_odata()` | `str` — e.g., `"Name eq 'John'"` |
| `& other` | `And` |
| `\| other` | `Or` |

### InList

```python
@dataclass(frozen=True, slots=True)
class InList:
    field: str
    values: tuple[ODataValue, ...]
```

| Method | Returns |
|--------|---------|
| `to_odata()` | `str` — e.g., `"(Status eq 'A' or Status eq 'B')"` |
| `& other` | `And` |
| `\| other` | `Or` |

### Raw

```python
@dataclass(frozen=True, slots=True)
class Raw:
    expression: str
```

Passthrough for OData syntax not covered by typed expressions.

| Method | Returns |
|--------|---------|
| `to_odata()` | `str` — the expression as-is |
| `& other` | `And` |
| `\| other` | `Or` |

### And

```python
@dataclass(frozen=True, slots=True)
class And:
    expressions: tuple[FilterExpression, ...]
```

Requires 2+ expressions. Chaining with `&` flattens.

| Method | Returns |
|--------|---------|
| `to_odata()` | `str` — e.g., `"(A eq 1 and B eq 2)"` |
| `& other` | `And` (flattened) |
| `\| other` | `Or` |

### Or

```python
@dataclass(frozen=True, slots=True)
class Or:
    expressions: tuple[FilterExpression, ...]
```

Requires 2+ expressions. Chaining with `|` flattens.

| Method | Returns |
|--------|---------|
| `to_odata()` | `str` — e.g., `"(A eq 1 or B eq 2)"` |
| `& other` | `And` |
| `\| other` | `Or` (flattened) |

---

## odyn.query.types

### ODataValue

```python
type ODataValue = str | int | float | bool | None | date | datetime
```

### VALID_OPERATORS

```python
VALID_OPERATORS: Final[frozenset[str]] = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})
```

---

## odyn.exceptions

### OdynError

```python
class OdynError(Exception)
```

Base exception for all Odyn errors.

### QueryValidationError

```python
class QueryValidationError(OdynError)
```

Invalid OData query construction.

### ConnectionError

```python
class ConnectionError(OdynError):
    url: str | None
    original_error: Exception | None
```

### TimeoutError

```python
class TimeoutError(ConnectionError):
    timeout: float | None
```

### SSLError

```python
class SSLError(ConnectionError)
```

### WebServiceError

```python
@dataclass
class WebServiceError(OdynError):
    message: str
    status_code: int
    url: str = ""
    response_body: str = ""
    odata_error: dict[str, Any] = field(default_factory=dict)
```

`str(e)` returns `"[{status_code}] {message}"`.

### AuthenticationError

```python
class AuthenticationError(WebServiceError)  # 401
```

### ForbiddenError

```python
class ForbiddenError(WebServiceError)  # 403
```

### NotFoundError

```python
class NotFoundError(WebServiceError)  # 404
```

### ValidationError

```python
class ValidationError(WebServiceError)  # 400
```

### ServerError

```python
class ServerError(WebServiceError)  # 5xx
```

### RateLimitError

```python
@dataclass
class RateLimitError(WebServiceError):
    retry_after: float | None = None  # 429
```

### RetryExhaustedError

```python
class RetryExhaustedError(OdynError):
    attempts: int
    last_exception: Exception
```
