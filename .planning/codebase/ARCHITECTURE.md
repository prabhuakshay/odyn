# Architecture

**Analysis Date:** 2026-03-22

## Pattern Overview

**Overall:** Layered async-first client architecture with fluent query builder DSL.

**Key Characteristics:**
- Async/await throughout with httpx for HTTP communication
- Factory pattern for client instantiation via `.create()` classmethod
- Fluent query builder with expression composition via operator overloading
- Multi-layer resilience: automatic retry, rate limiting, connection pooling, pagination
- Optional caching layer (Parquet-based) for query results
- Protocol-based authentication strategy pattern supporting multiple auth types

## Layers

**Presentation/API Layer:**
- Purpose: Exposes high-level query and fetch operations to consumers
- Location: `src/odyn/client.py` (public methods: `.get()`, `.get_stream()`, `.get_by_key()`, `.count()`, `.get_first()`, `.get_batch()`, etc.)
- Contains: Async context manager operations, request hooks, progress callbacks
- Depends on: Query builder, cache, auth, exceptions
- Used by: End user code, sync wrapper

**Query DSL Layer:**
- Purpose: Build OData filter expressions and query parameters fluently
- Location: `src/odyn/query/` (builder.py, fields.py, expressions.py)
- Contains: `ODataQuery` fluent builder, `Field` references via `F` singleton, filter expression classes
- Depends on: Type validation and value formatting
- Used by: Client layer for composing requests

**HTTP/Transport Layer:**
- Purpose: Handle HTTP communication with resilience
- Location: `src/odyn/client.py` (private methods: `._request()`, `._handle_response()`, `._apply_rate_limit()`)
- Contains: httpx AsyncClient, retry logic with exponential backoff, rate limiting via aiolimiter, concurrency semaphore
- Depends on: Auth, exception mapping
- Used by: Pagination layer

**Pagination Layer:**
- Purpose: Handle multi-page OData responses automatically
- Location: `src/odyn/client.py` (private methods: `._paginate()`, `._paginate_stream()`, `._fetch_page()`)
- Contains: Page fetching with automatic `$skiptoken` extraction, streaming iterator, progress callbacks
- Depends on: HTTP transport layer
- Used by: API layer methods (`.get()`, `.get_stream()`)

**Caching Layer (Optional):**
- Purpose: Store and retrieve query results with TTL expiration
- Location: `src/odyn/cache.py`
- Contains: `ParquetCache` for file-based caching with JSON metadata, `CacheMetadata` for expiration tracking
- Depends on: Polars DataFrames, pathlib
- Used by: HTTP layer (cache checks before requests, stores after success)

**Authentication Layer:**
- Purpose: Apply authentication credentials to outgoing requests
- Location: `src/odyn/auth.py`
- Contains: `BasicAuth` (base64-encoded credentials), `APIKeyAuth` (custom header), `AuthStrategy` type alias
- Depends on: httpx Request objects
- Used by: HTTP transport layer

**Exception Layer:**
- Purpose: Provide rich, structured error information
- Location: `src/odyn/exceptions.py`
- Contains: Exception hierarchy rooted at `OdynError` with specific subclasses for different failure modes
- Depends on: None (foundational)
- Used by: All layers for error signaling

**Sync Wrapper Layer:**
- Purpose: Enable blocking interface for non-async contexts
- Location: `src/odyn/sync.py`
- Contains: `BCWebServiceClientSync` that runs async operations in background thread
- Depends on: Async client, asyncio, threading
- Used by: Sync-only code

## Data Flow

**Query Execution (Happy Path):**

1. User constructs `ODataQuery()` with filters, selects, expansions via fluent API
2. User calls `.get(endpoint, query=query)` on `BCWebServiceClient`
3. Client checks cache (if enabled) using `ParquetCache.make_key(url, params)`
4. If cache miss, client calls `._request(method, url, params)` via retry loop
5. Retry loop calls `._apply_rate_limit()` (aiolimiter), then `._request()`
6. `_request()` applies auth via `auth.apply(request)`, makes httpx call
7. Response handler `_handle_response()` parses JSON, maps HTTP errors to OdynError exceptions
8. Response is cached via `cache.set(key, df, url, params)`
9. Client enters pagination loop via `._paginate()` for multi-page responses
10. For each page, `_fetch_page()` extracts `$skiptoken` from `@odata.nextLink`, fetches next
11. Progress callback invoked for each page
12. Final DataFrame returned to caller

**Streaming Flow:**

1. `.get_stream()` calls `._paginate_stream()` instead of `._paginate()`
2. Returns async iterator that yields one page at a time
3. Caller iterates with `async for page in stream:`
4. Same retry/rate limit logic applies per page

**Batch Operations:**

1. `.get_batch(values, batch_size)` splits values into chunks
2. For each batch, spawns `fetch_one_batch()` coroutines concurrently
3. Concurrency limited by semaphore (max_connections)
4. Results combined into single DataFrame
5. Batch progress callbacks invoked with success/failure stats

**State Management:**
- Immutable: Query builder returns `Self` for chaining, no state mutation
- Client state: Connection pool (httpx), semaphore, rate limiter stored as instance attributes
- Cache state: File system + in-memory hit/miss counters
- Pagination state: Managed per-request via loop variables, not persisted

## Key Abstractions

**ODataQuery:**
- Purpose: Represent a composable OData query without executing it
- Examples: `src/odyn/query/builder.py` (ODataQuery class)
- Pattern: Fluent builder with method chaining, immutable composition
- Generates: Dict of OData query parameters (`$filter`, `$select`, `$expand`, `$top`, `$skip`, `$orderby`, `$count`)

**Field / F Singleton:**
- Purpose: Provide type-safe field references for filter expressions
- Examples: `src/odyn/query/fields.py` (Field, _FieldFactory)
- Pattern: Singleton factory that creates Field instances via attribute access (e.g., `F.Status`)
- Composition: Operator overloading returns FilterExpression objects

**FilterExpression Protocol:**
- Purpose: Extensible interface for filter composition
- Examples: `src/odyn/query/expressions.py` (Comparison, InList, And, Or, Raw)
- Pattern: Protocol with `to_odata() -> str` method, composable via `&` (and) and `|` (or)
- Value types: `bool | int | float | str | date | datetime | None`

**AuthStrategy:**
- Purpose: Abstract authentication mechanism
- Examples: `src/odyn/auth.py` (BasicAuth, APIKeyAuth)
- Pattern: `frozen=True, slots=True` dataclass with `.apply(request)` method
- Union type: `BasicAuth | APIKeyAuth`

**ParquetCache:**
- Purpose: Provide fast file-based DataFrame caching with expiration
- Examples: `src/odyn/cache.py` (ParquetCache, CacheMetadata)
- Pattern: TTL-based expiration with SHA256 key derivation
- Storage: Two files per entry (`.parquet` data, `.json` metadata)

## Entry Points

**Factory Entry Point (Class Method):**
- Location: `src/odyn/client.py` - `BCWebServiceClient.create()`
- Triggers: User instantiation
- Responsibilities: Parse server/instance/company, construct base URL, initialize httpx client, configure rate limiter, set up logging

**Context Manager Entry Point:**
- Location: `src/odyn/client.py` - `__aenter__()`, `__aexit__()`
- Triggers: `async with BCWebServiceClient.create(...) as client:`
- Responsibilities: Ensure proper async resource cleanup

**Main API Entry Points:**
- `.get(endpoint, query=None)` - Fetch and return complete DataFrame
- `.get_stream(endpoint, query=None)` - Return async iterator of pages
- `.get_by_key(endpoint, key)` - Fetch single record by OData key predicate
- `.get_by_id(endpoint, id)` - Fetch single record by ID (convenience)
- `.get_first(endpoint, query=None)` - Fetch one record
- `.get_batch(endpoint, values, batch_size)` - Fetch multiple records by key in batches
- `.count(endpoint, query=None)` - Get record count with optional filter
- `.get_endpoints()` - List available OData endpoints

**Query Builder Entry Point:**
- Location: `src/odyn/query/__init__.py`
- Usage: `ODataQuery().select(...).filter(...).expand(...).order_by(...).top(...)`
- Returns: Query object passed to `.get()` method

## Error Handling

**Strategy:** Layered error handling with specific exception types for different failure modes.

**Patterns:**

1. **Query Validation Errors:**
   - Raised at query construction time (invalid field names, operators, values)
   - Exception: `QueryValidationError` (inherits from `OdynError`)
   - Examples: `F.InvalidField123!`, empty field names, unsupported types

2. **Connection Errors:**
   - Raised when network communication fails
   - Hierarchy: `ConnectionError` → `TimeoutError`, `SSLError`
   - Include original exception chain for debugging
   - Retryable: Yes (automatic exponential backoff)

3. **HTTP Status Code Errors:**
   - Base: `WebServiceError` with status_code, response_body, parsed odata_error dict
   - Specific: `AuthenticationError` (401), `ForbiddenError` (403), `NotFoundError` (404)
   - `ValidationError` (400), `RateLimitError` (429), `ServerError` (5xx)
   - Retryable: Yes for transient errors (429, 5xx); No for client errors (4xx except 429)

4. **Retry Exhaustion:**
   - Exception: `RetryExhaustedError` wraps last exception with attempt count
   - Raised when all max_retries attempts fail
   - Includes: attempts count, last_exception for root cause analysis

5. **Error Response Parsing:**
   - OData error objects parsed from `{ "error": { "code": "...", "message": "..." } }`
   - Fallback to HTTP status text if OData error missing
   - Method: `_extract_error_message()` handles both formats

## Cross-Cutting Concerns

**Logging:**
- Framework: Standard library `logging` module
- Logger name: `"odyn"` (configured at module level)
- Levels: INFO for major operations, DEBUG for detailed flow
- Configuration: `_configure_logging()` function with customizable level and format

**Validation:**
- Query field names: Alphanumeric + underscore, must start with letter/underscore
- Query operators: Only `eq, ne, gt, ge, lt, le` supported
- Query values: `bool, int, float, str, date, datetime, None` with strict type checking
- Validation functions: `_validate_field_name()`, `_validate_operator()`, `_validate_value()` in expressions.py

**Authentication:**
- Applied at request time via `auth.apply(request)` before each HTTP call
- BasicAuth: Base64-encoded Authorization header
- APIKeyAuth: Custom header (default X-API-Key)
- No authentication state stored between requests (stateless)

**Rate Limiting:**
- Framework: aiolimiter.AsyncLimiter
- Configurable: requests_per_minute (default 550/min, None to disable)
- Burst control: max_burst parameter prevents initial hammering (defaults to max_connections)
- Per-request: `await _apply_rate_limit()` called before each HTTP request

**Concurrency Control:**
- Semaphore: asyncio.Semaphore(max_connections) gates concurrent requests
- Connection pooling: httpx.Limits with max_connections and max_keepalive_connections
- Batch operations: Coroutines spawned up to max_connections, others queued

**Retry Logic:**
- Exponential backoff: base_delay * (2 ^ attempt) + jitter
- Jitter: ±10% random variation to prevent thundering herd
- Retry-After header: Honored if provided by rate limit error
- Configurable: max_retries (default 3), retry_backoff (default 1.0s)
- Retryable: Connection errors, 429, 5xx; Not retryable: auth/validation/client errors

---

*Architecture analysis: 2026-03-22*
