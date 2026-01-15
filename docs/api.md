# API Reference

This page provides a comprehensive reference for all public APIs in the Odyn library.

---

## Client Module (`odyn.client`)

### `BCWebServiceClient`

The main entry point for interacting with Business Central.

#### `BCWebServiceClient.create(...)`

Factory method to create a new client instance.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server` | `str` | *required* | The base URL of the Business Central server (e.g., `https://bc.example.com`). |
| `instance` | `str` | *required* | The Business Central instance name (e.g., `BC210`). |
| `auth` | `BasicAuth` | *required* | An instance of `BasicAuth` for authentication. |
| `company` | `str \| None` | `None` | Optional company name to scope all requests. |
| `timeout` | `float` | `30.0` | Request timeout in seconds. |
| `max_pages` | `int` | `100` | Maximum number of pages to fetch for paginated requests. |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates. |
| `cache_dir` | `Path \| str \| None` | `None` | Directory to store Parquet cache files. |
| `cache_ttl` | `int \| None` | `None` | Default time-to-live for cache entries in seconds. |
| `log_level` | `int` | `logging.INFO` | Logging level for the client. |
| `max_retries` | `int` | `3` | Maximum number of retry attempts for transient errors. |
| `retry_backoff` | `float` | `1.0` | Initial delay for exponential backoff. |
| `max_connections` | `int` | `4` | Maximum number of concurrent connections in the pool. |
| `requests_per_minute` | `float \| None` | `550.0` | Target requests per minute. Set to `None` to disable. |
| `max_burst` | `int \| None` | `None` | Maximum burst size (defaults to `max_connections`). Prevents server hammering on startup. |
| `on_request` | `RequestHook \| None` | `None` | Optional callback invoked before each HTTP request. |
| `on_response` | `ResponseHook \| None` | `None` | Optional callback invoked after each HTTP response. |

**Returns:** `BCWebServiceClient`

#### `await get(...)`

Fetches data from an OData endpoint.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `query` | `ODataQuery \| None` | `None` | Optional query builder instance. |
| `paginate` | `bool` | `True` | Whether to automatically follow next-page links. |
| `use_cache` | `bool` | `True` | Whether to attempt to use or update the cache. |
| `on_progress` | `ProgressCallback \| None` | `None` | Optional callback invoked after each page. |

**Returns:** `polars.DataFrame`

#### `get_stream(...)`

Returns an async iterator that yields DataFrames page-by-page.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `query` | `ODataQuery \| None` | `None` | Optional query builder instance. |
| `on_progress` | `ProgressCallback \| None` | `None` | Optional callback invoked after each page. |

**Returns:** `AsyncIterator[polars.DataFrame]`

#### `await get_by_key(...)`

Fetches a single record by its primary key.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `key` | `str` | *required* | The primary key value. |
| `select` | `list[str] \| None` | `None` | Optional list of fields to return. |

**Returns:** `dict[str, Any]`

#### `await get_by_id(...)`

Fetches a single record by its `SystemId` (GUID).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `system_id` | `str` | *required* | The SystemId GUID. |
| `select` | `list[str] \| None` | `None` | Optional list of fields to return. |

**Returns:** `dict[str, Any]`

#### `await count(...)`

Returns the total number of records matching a query.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `query` | `ODataQuery \| None` | `None` | Optional query builder instance. |

**Returns:** `int`

#### `await get_first(...)`

Fetches the first record matching a query.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `query` | `ODataQuery \| None` | `None` | Optional query builder instance. |

**Returns:** `dict[str, Any] \| None`

#### `await exists(...)`

Checks if a record exists by primary key.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `key` | `str` | *required* | The primary key value. |

**Returns:** `bool`

#### `await get_all(...)`

Optimized method to fetch all records using large batches.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `batch_size` | `int` | `1000` | Number of records to fetch per page. |

**Returns:** `polars.DataFrame`

#### `await get_batch(...)`

Concurrent batch fetch for records matching a list of values.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `field` | `str` | *required* | The field name to filter on. |
| `values` | `list` | *required* | Values to match (e.g., list of IDs). |
| `batch_size` | `int` | `50` | Values per concurrent request. |
| `select` | `list[str] \| None` | `None` | Fields to return. |
| `expand` | `list[str] \| None` | `None` | Related entities to expand. |
| `order_by` | `list[str] \| None` | `None` | Sort order. |
| `additional_filter` | `FilterExpression \| None` | `None` | Extra filter to AND with the IN-match. |
| `fail_fast` | `bool` | `False` | Raise immediately on first batch failure. |
| `use_cache` | `bool` | `True` | Whether to use the cache. |
| `on_progress` | `BatchProgressCallback \| None` | `None` | Optional callback invoked after each batch. |

**Returns:** `polars.DataFrame`

#### `await get_since(...)`

Fetches records modified since a timestamp (delta sync).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `timestamp` | `str` | *required* | ISO 8601 timestamp (e.g., `2024-01-15T10:30:00Z`). |
| `query` | `ODataQuery \| None` | `None` | Optional additional query. |
| `use_cache` | `bool` | `False` | Whether to cache results (default False for fresh data). |
| `on_progress` | `ProgressCallback \| None` | `None` | Optional callback invoked after each page. |

**Returns:** `polars.DataFrame`

#### `await get_before(...)`

Fetches records modified before a timestamp.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `timestamp` | `str` | *required* | ISO 8601 timestamp (e.g., `2024-01-15T10:30:00Z`). |
| `query` | `ODataQuery \| None` | `None` | Optional additional query. |
| `use_cache` | `bool` | `True` | Whether to cache results (default True for historical data). |
| `on_progress` | `ProgressCallback \| None` | `None` | Optional callback invoked after each page. |

**Returns:** `polars.DataFrame`

#### `await get_endpoints()`

Lists all available OData entity sets on the server.

**Returns:** `list[str]`

---

## Authentication Module (`odyn.auth`)

### `BasicAuth`

Handles HTTP Basic Authentication.

| Attribute | Type | Description |
|-----------|------|-------------|
| `username` | `str` | The username (including domain if required). |
| `password` | `str` | The password (masked in `__repr__`). |
| `auth_header` | `str` | (Property) The Base64 encoded `Authorization` header. |

---

## Query Module (`odyn.query`)

### `ODataQuery`

Fluent builder for OData URL parameters.

| Method | Returns | Description |
|--------|---------|-------------|
| `select(*fields)` | `Self` | Selects specific fields to return. |
| `filter(expression)` | `Self` | Adds a filter expression. Multiple calls are joined with `and`. |
| `filter_raw(odata_str)` | `Self` | Adds a raw OData filter string. |
| `expand(*relations)` | `Self` | Expands navigation properties. |
| `order_by(*fields)` | `Self` | Sets the sort order (e.g., `"Name asc"`). |
| `top(n)` | `Self` | Limits the number of records returned. |
| `skip(n)` | `Self` | Skips the first `n` records. |
| `count(include=True)` | `Self` | Includes the total count in the response. |
| `build()` | `dict[str, str]` | Generates the dictionary of URL parameters. |

### `F` (Field Proxy)

A convenience object for creating `Field` instances via attribute access (e.g., `F.No`, `F.Name`).

### `Field`

Represents a field in a filter expression.

| Method | Returns | Description |
|--------|---------|-------------|
| `is_in(values)` | `FilterExpression` | Checks if the field value is in a list of values. |

**Operators:** Supports `==`, `!=`, `<`, `<=`, `>`, `>=` returning `FilterExpression`.

---

## Cache Module (`odyn.cache`)

### `ParquetCache`

Persistent storage for DataFrames.

| Method | Returns | Description |
|--------|---------|-------------|
| `get(key)` | `DataFrame \| None` | Retrieves a DataFrame from the cache. |
| `set(key, df, ...)` | `None` | Saves a DataFrame to the cache. |
| `delete(key)` | `bool` | Deletes a cache entry. |
| `cleanup()` | `int` | Removes expired cache entries. |
| `clear()` | `int` | Removes all cache entries. |
| `size` | `int` | (Property) Number of entries in the cache. |
| `stats()` | `dict[str, int]` | Returns cache statistics (hits, misses, disk_bytes). |

---

## Exceptions Module (`odyn.exceptions`)

| Exception | Base | Description |
|-----------|------|-------------|
| `OdynError` | `Exception` | Base class for all library exceptions. |
| `OdynConnectionError` | `OdynError` | Network connection issues. |
| `OdynTimeoutError` | `OdynConnectionError` | Request timed out. |
| `OdynSSLError` | `OdynConnectionError` | SSL certificate verification failed. |
| `WebServiceError` | `OdynError` | API returned a non-success status code. |
| `AuthenticationError` | `WebServiceError` | HTTP 401 Unauthorized. |
| `ForbiddenError` | `WebServiceError` | HTTP 403 Forbidden. |
| `NotFoundError` | `WebServiceError` | HTTP 404 Not Found. |
| `ValidationError` | `WebServiceError` | HTTP 400 Bad Request. |
| `RateLimitError` | `WebServiceError` | HTTP 429 Too Many Requests. |
| `ServerError` | `WebServiceError` | HTTP 5xx Server Error. |
| `RetryExhaustedError` | `OdynError` | Max retries reached without success. |
| `QueryValidationError` | `OdynError` | Invalid OData query construction. |

---

## Sync Module (`odyn.sync`)

### `BCWebServiceClientSync`

Synchronous wrapper for `BCWebServiceClient`. Provides blocking versions of all async methods, using a background thread with its own event loop.

#### `BCWebServiceClientSync.create(...)`

Factory method with identical parameters to `BCWebServiceClient.create()`.

**Returns:** `BCWebServiceClientSync`

All methods mirror `BCWebServiceClient` but block until completion:

| Method | Returns | Description |
|--------|---------|-------------|
| `get(...)` | `DataFrame` | Blocking version of `await client.get()`. |
| `get_stream(...)` | N/A | Not available (use async client for streaming). |
| `get_by_key(...)` | `dict` | Blocking version of `await client.get_by_key()`. |
| `get_by_id(...)` | `dict` | Blocking version of `await client.get_by_id()`. |
| `count(...)` | `int` | Blocking version of `await client.count()`. |
| `get_first(...)` | `dict \| None` | Blocking version of `await client.get_first()`. |
| `exists(...)` | `bool` | Blocking version of `await client.exists()`. |
| `get_since(...)` | `DataFrame` | Blocking version of `await client.get_since()`. |
| `get_before(...)` | `DataFrame` | Blocking version of `await client.get_before()`. |
| `get_all(...)` | `DataFrame` | Blocking version of `await client.get_all()`. |
| `get_batch(...)` | `DataFrame` | Blocking version of `await client.get_batch()`. |
| `close()` | `None` | Closes the client and background thread. |

Supports context manager protocol:

```python
with BCWebServiceClientSync.create(...) as client:
    df = client.get("customers")
```

---

## Callback Protocols (`odyn.client`)

### `ProgressCallback`

Protocol for pagination progress callbacks.

```python
def on_progress(*, page: int, records_on_page: int, total_records: int, is_final: bool) -> None:
    ...
```

### `BatchProgressCallback`

Protocol for batch operation progress callbacks.

```python
def on_progress(*, batch: int, total_batches: int, successful: int, failed: int, is_final: bool) -> None:
    ...
```

### `RequestHook`

Protocol for request hooks (called before each HTTP request).

```python
def on_request(*, method: str, url: str, params: dict[str, str] | None) -> None:
    ...
```

### `ResponseHook`

Protocol for response hooks (called after each HTTP response).

```python
def on_response(*, method: str, url: str, status_code: int, duration_ms: float) -> None:
    ...
```
