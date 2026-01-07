# Exceptions Guide

Odyn uses a hierarchical exception system to help you catch and handle specific error conditions gracefully.

## Exception Hierarchy

- `OdynError` (Base)
    - `OdynConnectionError` - Network-level issues.
        - `OdynTimeoutError` - Request timed out.
        - `OdynSSLError` - SSL certificate validation failed.
    - `WebServiceError` - The server returned a non-success HTTP status code.
        - `AuthenticationError` (401)
        - `ForbiddenError` (403)
        - `NotFoundError` (404)
        - `ValidationError` (400)
        - `RateLimitError` (429) - Too many requests.
        - `ServerError` (5xx) - Internal server error.
    - `RetryExhaustedError` - Max retry attempts reached.
    - `QueryValidationError` - Error building the OData query string.

## Handling Errors

You can catch the base `OdynError` to handle any library-related issue, or get more specific.

```python
from odyn import OdynError, NotFoundError

try:
    df = await client.get("invalid_endpoint")
except NotFoundError:
    print("The entity set does not exist.")
except OdynError as e:
    print(f"An unexpected Odyn error occurred: {e}")
```

## Rich Error Context

The `WebServiceError` (and its subclasses) contains detailed information about the failed request:

- `status_code`: The HTTP status code returned by the server.
- `message`: A descriptive error message from Odyn or the server.
- `url`: The full URL of the failed request.
- `response_body`: The raw response body from the server.
- `odata_error`: A dictionary containing the parsed OData error message (if available).

## Retries and Timeouts

Errors like `OdynTimeoutError` and `ServerError` are automatically retried by the client before being raised. If the error persists through all retry attempts, `RetryExhaustedError` is raised, with the `last_exception` attribute pointing to the final failure.
