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
| `max_connections` | `int` | `5` | Maximum number of concurrent connections in the pool. |
| `rate_limit` | `float \| None` | `10.0` | Target requests per second. Set to `None` to disable. |

**Returns:** `BCWebServiceClient`

#### `await get(...)`

Fetches data from an OData endpoint.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `query` | `ODataQuery \| None` | `None` | Optional query builder instance. |
| `paginate` | `bool` | `True` | Whether to automatically follow next-page links. |
| `use_cache` | `bool` | `True` | Whether to attempt to use or update the cache. |

**Returns:** `polars.DataFrame`

#### `get_stream(...)`

Returns an async iterator that yields DataFrames page-by-page.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | `str` | *required* | The OData entity set name. |
| `query` | `ODataQuery \| None` | `None` | Optional query builder instance. |

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
| `NotFoundError` | `WebServiceError` | HTTP 404 Not Found. |
| `RateLimitError` | `WebServiceError` | HTTP 429 Too Many Requests. |
| `RetryExhaustedError` | `OdynError` | Max retries reached without success. |
| `QueryValidationError` | `OdynError` | Invalid OData query construction. |
