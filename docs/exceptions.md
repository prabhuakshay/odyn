# Exceptions

Odyn uses a hierarchical exception system rooted at `OdynError`. Every exception Odyn raises inherits from this base, so you can catch everything with a single `except OdynError` or handle specific error types.

## Exception Hierarchy

```
OdynError (base)
├── QueryValidationError          — invalid OData query construction
├── RetryExhaustedError           — all retry attempts failed
├── ConnectionError               — network/connection issues
│   ├── TimeoutError              — request timeout
│   └── SSLError                  — SSL/TLS issues
└── WebServiceError               — Business Central API errors (4xx/5xx)
    ├── AuthenticationError       — HTTP 401
    ├── ForbiddenError            — HTTP 403
    ├── NotFoundError             — HTTP 404
    ├── ValidationError           — HTTP 400
    ├── RateLimitError            — HTTP 429
    └── ServerError               — HTTP 5xx
```

## Import

All exceptions are available from the top-level package:

```python
from odyn import (
    OdynError,
    QueryValidationError,
    RetryExhaustedError,
    OdynConnectionError,   # aliased to avoid shadowing builtins
    OdynTimeoutError,      # aliased
    OdynSSLError,          # aliased
    WebServiceError,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)
```

Note: `ConnectionError`, `TimeoutError`, and `SSLError` shadow Python builtins, so they're re-exported with `Odyn` prefixes. You can also import the unaliased names from `odyn.exceptions` directly.

## Exception Details

### OdynError

Base exception. Catch this to handle any Odyn error.

```python
try:
    df = await client.get("customers")
except OdynError as e:
    logger.error(f"Odyn operation failed: {e}")
```

### QueryValidationError

Raised during query construction for invalid field names, operators, or values.

```python
from odyn.query import F

# These raise QueryValidationError:
F.Field("123invalid")           # name must start with letter/underscore
ODataQuery().top(-1)            # negative top
ODataQuery().select("")         # empty field name
ODataQuery().filter("raw str")  # must use filter_raw() for strings
```

### ConnectionError

Base for network issues. Has `url` and `original_error` attributes.

```python
try:
    df = await client.get("customers")
except OdynConnectionError as e:
    print(f"URL: {e.url}")
    print(f"Underlying error: {e.original_error}")
```

### TimeoutError

Extends `ConnectionError`. Adds `timeout` attribute.

```python
try:
    df = await client.get("customers")
except OdynTimeoutError as e:
    print(f"Timed out after {e.timeout}s on {e.url}")
```

### SSLError

Extends `ConnectionError`. Raised for certificate verification failures. Not retried.

```python
try:
    df = await client.get("customers")
except OdynSSLError:
    print("SSL error — try verify_ssl=False for self-signed certs")
```

### WebServiceError

Base for API errors (HTTP 4xx/5xx). A dataclass with rich error information.

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | `str` | Error message (from OData error or HTTP reason phrase) |
| `status_code` | `int` | HTTP status code |
| `url` | `str` | The URL that returned the error |
| `response_body` | `str` | Raw response body |
| `odata_error` | `dict[str, Any]` | Parsed OData error object (if available) |

```python
try:
    df = await client.get("invalidEndpoint")
except WebServiceError as e:
    print(f"[{e.status_code}] {e.message}")
    print(f"URL: {e.url}")
    print(f"OData error: {e.odata_error}")
```

`str(e)` returns `"[{status_code}] {message}"`.

### AuthenticationError

HTTP 401. Invalid credentials. Not retried.

```python
try:
    df = await client.get("customers")
except AuthenticationError:
    print("Check username and password")
```

### ForbiddenError

HTTP 403. Authenticated but not authorized. Not retried.

### NotFoundError

HTTP 404. Invalid endpoint or non-existent record. Not retried.

```python
try:
    record = await client.get_by_key("customers", "DOESNTEXIST")
except NotFoundError as e:
    print(f"Not found: {e.message}")
```

### ValidationError

HTTP 400. Malformed query or invalid request. Not retried.

### RateLimitError

HTTP 429. Extends `WebServiceError` with a `retry_after` attribute.

| Attribute | Type | Description |
|-----------|------|-------------|
| `retry_after` | `float \| None` | Seconds to wait (from `Retry-After` header) |

Automatically retried by the client (respects `Retry-After`).

```python
try:
    df = await client.get("customers")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}s")
```

### ServerError

HTTP 5xx. Server-side issue. Automatically retried.

### RetryExhaustedError

Raised after all retry attempts fail for a retryable error.

| Attribute | Type | Description |
|-----------|------|-------------|
| `attempts` | `int` | Total number of attempts made |
| `last_exception` | `Exception` | The last exception that triggered retry |

```python
try:
    df = await client.get("customers")
except RetryExhaustedError as e:
    print(f"Failed after {e.attempts} attempts")
    print(f"Last error: {e.last_exception}")
```

## Retry Behavior

| Exception | Retried? | Notes |
|-----------|----------|-------|
| `TimeoutError` | Yes | |
| `ConnectionError` | Yes | |
| `RateLimitError` (429) | Yes | Respects `Retry-After` header |
| `ServerError` (5xx) | Yes | |
| `AuthenticationError` (401) | No | Raised immediately |
| `ForbiddenError` (403) | No | Raised immediately |
| `NotFoundError` (404) | No | Raised immediately |
| `ValidationError` (400) | No | Raised immediately |
| `SSLError` | No | Raised immediately |

## Error Handling Patterns

### Catch everything

```python
try:
    df = await client.get("customers")
except OdynError as e:
    logger.error(f"Operation failed: {e}")
```

### Catch by category

```python
try:
    df = await client.get("customers")
except AuthenticationError:
    # handle auth issues
except NotFoundError:
    # handle missing endpoint
except WebServiceError as e:
    # handle other API errors
except OdynConnectionError:
    # handle network issues
except RetryExhaustedError as e:
    # all retries failed
```

### Graceful fallback with exists()

```python
if await client.exists("customers", customer_id):
    record = await client.get_by_key("customers", customer_id)
else:
    record = None
```

### Batch error handling

```python
# fail_fast=False (default): log errors, continue other batches
df = await client.get_batch("customers", "No", ids, fail_fast=False)

# fail_fast=True: raise on first error
try:
    df = await client.get_batch("customers", "No", ids, fail_fast=True)
except RetryExhaustedError:
    print("A batch failed after retries")
```
