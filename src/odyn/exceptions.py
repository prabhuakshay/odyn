"""Exception hierarchy for Odyn.

This module defines a rich exception hierarchy for all Odyn operations,
providing detailed error information for debugging and error handling.

Exception Hierarchy:
    OdynError (base)
    ├── QueryValidationError - Invalid OData query construction
    ├── RetryExhaustedError - All retry attempts failed
    ├── ConnectionError - Network/connection issues
    │   ├── TimeoutError - Request timeout
    │   └── SSLError - SSL/TLS issues
    ├── AuthenticationError - 401 responses
    ├── WebServiceError - Business Central API errors
    │   ├── NotFoundError - 404 responses
    │   ├── ValidationError - 400 responses (bad request)
    │   ├── ForbiddenError - 403 responses
    │   ├── RateLimitError - 429 responses (too many requests)
    │   └── ServerError - 5xx responses

Example:
    >>> from odyn.exceptions import AuthenticationError, NotFoundError
    >>> try:
    ...     data = await client.get("invalid_endpoint")
    ... except NotFoundError as e:
    ...     print(f"Endpoint not found: {e}")
    ... except AuthenticationError as e:
    ...     print(f"Auth failed: {e}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AuthenticationError",
    "ConnectionError",
    "ForbiddenError",
    "NotFoundError",
    "OdynError",
    "QueryValidationError",
    "RateLimitError",
    "RetryExhaustedError",
    "SSLError",
    "ServerError",
    "TimeoutError",
    "ValidationError",
    "WebServiceError",
]


class OdynError(Exception):
    """Base exception for all Odyn errors.

    All Odyn exceptions inherit from this class, allowing you to catch
    any Odyn-related error with a single except clause.

    Example:
        >>> try:
        ...     await client.get("customers")
        ... except OdynError as e:
        ...     logger.error(f"Odyn operation failed: {e}")
    """


class QueryValidationError(OdynError):
    """Raised when OData query validation fails.

    This error is raised during query construction when invalid
    field names, operators, or values are provided.

    Example:
        >>> from odyn.query import F
        >>> F.InvalidField123!  # Raises QueryValidationError
    """


class ConnectionError(OdynError):  # noqa: A001
    """Base class for connection-related errors.

    Raised when there are network issues preventing communication
    with the Business Central server.

    Attributes:
        url: The URL that was being accessed.
        original_error: The underlying exception, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize the connection error.

        Args:
            message: Human-readable error description.
            url: The URL that was being accessed.
            original_error: The underlying exception.
        """
        super().__init__(message)
        self.url = url
        self.original_error = original_error


class TimeoutError(ConnectionError):  # noqa: A001
    """Raised when a request times out.

    Attributes:
        timeout: The timeout value in seconds.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        timeout: float | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize the timeout error.

        Args:
            message: Human-readable error description.
            url: The URL that timed out.
            timeout: The timeout value in seconds.
            original_error: The underlying exception.
        """
        super().__init__(message, url=url, original_error=original_error)
        self.timeout = timeout


class SSLError(ConnectionError):
    """Raised when SSL/TLS errors occur.

    This typically happens with self-signed certificates or
    certificate verification failures.
    """


@dataclass
class WebServiceError(OdynError):
    """Base class for Business Central Web Service API errors.

    Raised when the API returns an error response (4xx or 5xx status codes).

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code (e.g., 400, 404, 500).
        url: The URL that was accessed.
        response_body: The raw response body, if available.
        odata_error: Parsed OData error details, if available.
    """

    message: str
    status_code: int
    url: str = ""
    response_body: str = ""
    odata_error: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Format the error message with status code."""
        return f"[{self.status_code}] {self.message}"


class AuthenticationError(WebServiceError):
    """Raised when authentication fails (HTTP 401).

    This indicates invalid credentials or expired authentication.

    Example:
        >>> try:
        ...     await client.get("customers")
        ... except AuthenticationError:
        ...     print("Check your username and password")
    """


class ForbiddenError(WebServiceError):
    """Raised when access is forbidden (HTTP 403).

    The user is authenticated but lacks permission to access the resource.
    """


class NotFoundError(WebServiceError):
    """Raised when the requested resource is not found (HTTP 404).

    This could indicate an invalid endpoint name or a non-existent record ID.

    Example:
        >>> try:
        ...     await client.get_by_id("customers", "invalid-id")
        ... except NotFoundError as e:
        ...     print(f"Customer not found: {e}")
    """


class ValidationError(WebServiceError):
    """Raised when the request is invalid (HTTP 400).

    This typically indicates malformed OData queries or invalid request data.
    """


class ServerError(WebServiceError):
    """Raised when the server encounters an error (HTTP 5xx).

    This indicates an issue on the Business Central server side.
    Retrying after a delay may succeed.
    """


@dataclass
class RateLimitError(WebServiceError):
    """Raised when rate limiting is triggered (HTTP 429).

    This indicates too many requests have been sent to the server.
    The client will automatically retry after the rate limit resets
    if retry is enabled.

    Attributes:
        retry_after: Number of seconds to wait before retrying, if provided.

    Example:
        >>> try:
        ...     await client.get("customers")
        ... except RateLimitError as e:
        ...     print(f"Rate limited, retry after {e.retry_after}s")
    """

    retry_after: float | None = None


class RetryExhaustedError(OdynError):
    """Raised when all retry attempts have been exhausted.

    This wraps the last exception that caused the retry to fail.

    Attributes:
        attempts: Number of retry attempts made.
        last_exception: The last exception that triggered the retry.

    Example:
        >>> try:
        ...     await client.get("customers")
        ... except RetryExhaustedError as e:
        ...     print(f"Failed after {e.attempts} attempts: {e.last_exception}")
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        last_exception: Exception,
    ) -> None:
        """Initialize the retry exhausted error.

        Args:
            message: Human-readable error description.
            attempts: Number of retry attempts made.
            last_exception: The last exception that triggered the retry.
        """
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception
