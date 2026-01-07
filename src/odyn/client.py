"""Async client for Business Central on-premises Web Services.

This module provides a modern, async-first client for interacting with
Microsoft Dynamics 365 Business Central on-premises OData web services.

Features:
    - Async/await support with httpx
    - HTTP and HTTPS support (configurable SSL verification)
    - Automatic retry with exponential backoff
    - Rate limiting to prevent overwhelming the server
    - Concurrent request limits for connection pooling
    - Automatic pagination with streaming
    - Parquet-based caching for fast repeat queries
    - Rich structured logging
    - Fluent OData query builder integration
    - Context manager support for automatic cleanup
    - Polars DataFrame responses for efficient data handling

Example:
    >>> from odyn import BCWebServiceClient, BasicAuth
    >>> from odyn.query import ODataQuery, F
    >>>
    >>> async with BCWebServiceClient.create(
    ...     server="https://bc-server:7048",
    ...     instance="BC210",
    ...     company="CRONUS",
    ...     auth=BasicAuth("user", "pass"),
    ... ) as client:
    ...     # Simple query
    ...     customers = await client.get("customers")
    ...
    ...     # With OData query builder
    ...     query = ODataQuery().filter(F.Balance > 1000).top(10)
    ...     top_customers = await client.get("customers", query=query)
    ...
    ...     # Get single record
    ...     customer = await client.get_by_key("customers", "C001")
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import httpx
import polars as pl

from odyn.cache import ParquetCache
from odyn.exceptions import (
    AuthenticationError,
    ConnectionError as OdynConnectionError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    RetryExhaustedError,
    ServerError,
    SSLError as OdynSSLError,
    TimeoutError as OdynTimeoutError,
    ValidationError,
    WebServiceError,
)
from odyn.query import Field, ODataQuery

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from odyn.auth import BasicAuth
    from odyn.query.expressions import FilterExpression

__all__ = [
    "BCWebServiceClient",
]

# Create a logger for the client
logger = logging.getLogger("odyn.client")


def _configure_logging(
    level: int = logging.INFO,
    *,
    format_string: str | None = None,
) -> None:
    """Configure logging for the Odyn client.

    Args:
        level: The logging level (default: INFO).
        format_string: Custom format string for log messages.
    """
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format_string))

    # Configure the odyn logger
    odyn_logger = logging.getLogger("odyn")
    odyn_logger.setLevel(level)
    odyn_logger.addHandler(handler)
    odyn_logger.propagate = False


@dataclass
class BCWebServiceClient:
    """Async client for Business Central on-premises Web Services.

    This client provides async access to Business Central OData endpoints
    with automatic pagination, caching, retry logic, rate limiting, and
    concurrent request management.

    Attributes:
        base_url: The base URL for the BC web service.
        auth: Authentication handler (BasicAuth).
        company: Company name for scoping requests.
        timeout: Request timeout in seconds.
        max_pages: Maximum pages to fetch during auto-pagination.
        verify_ssl: Whether to verify SSL certificates.
        cache: Optional ParquetCache for query result caching.
        max_retries: Maximum retry attempts for transient failures (default: 3).
        retry_backoff: Base delay in seconds for exponential backoff (default: 1.0).
        max_connections: Maximum concurrent connections (default: 5).
        rate_limit: Maximum requests per second (default: 10.0, None to disable).

    Example:
        >>> async with BCWebServiceClient.create(
        ...     server="https://bc-server:7048",
        ...     instance="BC210",
        ...     company="CRONUS",
        ...     auth=BasicAuth("user", "pass"),
        ... ) as client:
        ...     df = await client.get("customers")
    """

    base_url: str
    auth: BasicAuth
    company: str | None = None
    timeout: float = 30.0
    max_pages: int = 100
    verify_ssl: bool = True
    cache: ParquetCache | None = None

    # Retry configuration
    max_retries: int = 3
    retry_backoff: float = 1.0

    # Concurrency and rate limiting
    max_connections: int = 5
    rate_limit: float | None = 10.0  # requests per second

    _http: httpx.AsyncClient = field(init=False, repr=False)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)
    _rate_limit_lock: asyncio.Lock = field(init=False, repr=False)
    _last_request_time: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self) -> None:
        """Initialize the HTTP client with connection limits."""
        # Configure connection limits
        limits = httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_connections,
        )

        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            verify=self.verify_ssl,
            limits=limits,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": self.auth.auth_header,
            },
        )

        # Initialize concurrency controls
        self._semaphore = asyncio.Semaphore(self.max_connections)
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0

        logger.info(
            "Client initialized: base_url=%s, company=%s, verify_ssl=%s, "
            "max_retries=%d, max_connections=%d, rate_limit=%s",
            self.base_url,
            self.company,
            self.verify_ssl,
            self.max_retries,
            self.max_connections,
            f"{self.rate_limit} req/s" if self.rate_limit else "disabled",
        )

    @classmethod
    def create(
        cls,
        server: str,
        instance: str,
        auth: BasicAuth,
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
        max_connections: int = 5,
        rate_limit: float | None = 10.0,
    ) -> BCWebServiceClient:
        r"""Create a client for Business Central on-premises web services.

        This is the recommended factory method for creating a client instance.
        It handles URL construction and optional cache setup.

        Args:
            server: Server URL (e.g., "https://bc-server:7048" or "http://bc-server:7048").
            instance: BC instance name (e.g., "BC210", "BC230").
            auth: Authentication strategy (BasicAuth).
            company: Optional company name to scope all requests.
            timeout: Request timeout in seconds (default: 30).
            max_pages: Maximum pages to fetch during auto-pagination (default: 100).
            verify_ssl: Whether to verify SSL certificates (default: True).
                        Set to False for self-signed certificates.
            cache_dir: Optional directory for Parquet cache.
            cache_ttl: Optional cache TTL in seconds.
            log_level: Logging level (default: INFO).
            max_retries: Maximum retry attempts for transient failures (default: 3).
                         Retries are attempted for timeouts, connection errors,
                         rate limits (429), and server errors (5xx).
            retry_backoff: Base delay in seconds for exponential backoff (default: 1.0).
                           Actual delay = backoff * (2 ** attempt) + jitter.
            max_connections: Maximum concurrent connections to the server (default: 5).
                             Business Central on-premises typically handles 5-10
                             concurrent connections well.
            rate_limit: Maximum requests per second (default: 10.0).
                        Set to None to disable rate limiting.
                        Default of 10 req/s is conservative for BC on-premises.

        Returns:
            Configured BCWebServiceClient instance.

        Example:
            >>> client = BCWebServiceClient.create(
            ...     server="https://bc-server:7048",
            ...     instance="BC210",
            ...     auth=BasicAuth("DOMAIN\\user", "password"),
            ...     company="CRONUS International Ltd.",
            ...     verify_ssl=False,  # For self-signed certs
            ...     cache_dir="~/.cache/odyn",
            ...     cache_ttl=3600,  # 1 hour
            ...     max_retries=5,  # More retries for flaky networks
            ...     rate_limit=5.0,  # Slower rate for busy servers
            ... )
        """
        _configure_logging(log_level)

        # Normalize server URL
        server = server.rstrip("/")

        # Build OData endpoint URL: {server}/{instance}/ODataV4
        base_url = f"{server}/{instance}/ODataV4"

        # Setup cache if requested
        cache = None
        if cache_dir is not None:
            cache_path = Path(cache_dir).expanduser()
            cache = ParquetCache(cache_path, default_ttl=cache_ttl)
            logger.info("Cache enabled: dir=%s, ttl=%s", cache_path, cache_ttl)

        return cls(
            base_url=base_url,
            auth=auth,
            company=company,
            timeout=timeout,
            max_pages=max_pages,
            verify_ssl=verify_ssl,
            cache=cache,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            max_connections=max_connections,
            rate_limit=rate_limit,
        )

    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for an endpoint.

        Args:
            endpoint: The OData entity set name (e.g., "customers").

        Returns:
            Full URL including company context if set.
        """
        endpoint = endpoint.lstrip("/")

        # Company is added as a filter or path parameter
        if self.company:
            return f"{self.base_url}/Company('{self.company}')/{endpoint}"
        return f"{self.base_url}/{endpoint}"

    async def _handle_response(self, response: httpx.Response, url: str) -> dict[str, Any]:
        """Handle the HTTP response, raising appropriate exceptions for errors.

        Args:
            response: The httpx response object.
            url: The URL that was requested (for error context).

        Returns:
            Parsed JSON response body.

        Raises:
            AuthenticationError: For 401 responses.
            ForbiddenError: For 403 responses.
            NotFoundError: For 404 responses.
            ValidationError: For 400 responses.
            ServerError: For 5xx responses.
            WebServiceError: For other error responses.
        """
        if response.is_success:
            if response.status_code == 204:
                return {}
            return response.json()

        # Parse error body
        error_body = ""
        odata_error: dict[str, Any] = {}
        try:
            error_body = response.text
            error_json = response.json()
            odata_error = error_json.get("error", {})
        except (ValueError, KeyError):
            # JSON parsing failed, use text body
            pass

        # Extract message from OData error format
        message = self._extract_error_message(odata_error, error_body or response.reason_phrase)

        # Map status codes to exceptions
        exception_map: dict[int, type[WebServiceError]] = {
            400: ValidationError,
            401: AuthenticationError,
            403: ForbiddenError,
            404: NotFoundError,
        }

        if response.status_code in exception_map:
            exc_class = exception_map[response.status_code]
            logger.warning(
                "API error: status=%d, url=%s, message=%s",
                response.status_code,
                url,
                message,
            )
            raise exc_class(
                message=message,
                status_code=response.status_code,
                url=url,
                response_body=error_body,
                odata_error=odata_error,
            )

        # Handle rate limiting (429)
        if response.status_code == 429:
            retry_after = None
            retry_header = response.headers.get("Retry-After")
            if retry_header:
                with contextlib.suppress(ValueError):
                    retry_after = float(retry_header)
            logger.warning(
                "Rate limited: status=429, url=%s, retry_after=%s",
                url,
                retry_after,
            )
            raise RateLimitError(
                message=message or "Rate limit exceeded",
                status_code=429,
                url=url,
                response_body=error_body,
                odata_error=odata_error,
                retry_after=retry_after,
            )

        if response.status_code >= 500:
            logger.error(
                "Server error: status=%d, url=%s, message=%s",
                response.status_code,
                url,
                message,
            )
            raise ServerError(
                message=message,
                status_code=response.status_code,
                url=url,
                response_body=error_body,
                odata_error=odata_error,
            )

        logger.warning(
            "Unexpected error: status=%d, url=%s, message=%s",
            response.status_code,
            url,
            message,
        )
        raise WebServiceError(
            message=message,
            status_code=response.status_code,
            url=url,
            response_body=error_body,
            odata_error=odata_error,
        )

    def _extract_error_message(self, odata_error: dict[str, Any], fallback: str) -> str:
        """Extract error message from OData error response.

        Args:
            odata_error: The parsed OData error object.
            fallback: Fallback message if extraction fails.

        Returns:
            The extracted or fallback error message.
        """
        if isinstance(odata_error, dict):
            return odata_error.get("message", fallback)
        return fallback

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting by waiting if necessary.

        This ensures requests don't exceed the configured rate limit.
        Uses a lock to prevent race conditions when tracking time.
        """
        if self.rate_limit is None:
            return

        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            min_interval = 1.0 / self.rate_limit
            elapsed = now - self._last_request_time

            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                logger.debug("Rate limiting: waiting %.3fs", wait_time)
                await asyncio.sleep(wait_time)

            self._last_request_time = asyncio.get_event_loop().time()

    def _is_retryable(self, exc: Exception) -> bool:
        """Check if an exception is retryable.

        Args:
            exc: The exception to check.

        Returns:
            True if the exception is retryable, False otherwise.
        """
        # Retry on connection errors and timeouts
        if isinstance(exc, (OdynTimeoutError, OdynConnectionError)):
            return True

        # Retry on rate limit errors
        if isinstance(exc, RateLimitError):
            return True

        # Retry on server errors (5xx)
        return isinstance(exc, ServerError)

    def _calculate_backoff(self, attempt: int, retry_after: float | None = None) -> float:
        """Calculate the backoff delay for a retry attempt.

        Uses exponential backoff with jitter to prevent thundering herd.

        Args:
            attempt: The current attempt number (0-indexed).
            retry_after: Optional server-specified delay (from 429 response).

        Returns:
            Delay in seconds before the next retry.
        """
        if retry_after is not None:
            return retry_after

        # Exponential backoff: base * 2^attempt + jitter
        base_delay = self.retry_backoff * (2**attempt)
        jitter = random.uniform(0, self.retry_backoff)  # noqa: S311  # nosec B311
        return base_delay + jitter

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with retry, rate limiting, and error handling.

        This method implements:
        - Rate limiting to prevent overwhelming the server
        - Concurrency control via semaphore
        - Automatic retry with exponential backoff for transient errors
        - Proper error classification and exception raising

        Args:
            method: HTTP method (GET, POST, etc.).
            url: The full URL to request.
            params: Optional query parameters.
            json_body: Optional JSON request body.

        Returns:
            Parsed JSON response.

        Raises:
            RetryExhaustedError: When all retry attempts fail.
            OdynConnectionError: For network errors (if not retried).
            OdynTimeoutError: For request timeouts (if not retried).
            OdynSSLError: For SSL/TLS errors (not retried).
            AuthenticationError: For 401 responses (not retried).
            ForbiddenError: For 403 responses (not retried).
            NotFoundError: For 404 responses (not retried).
            ValidationError: For 400 responses (not retried).
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # Apply rate limiting
                await self._apply_rate_limit()

                # Acquire semaphore for concurrency control
                async with self._semaphore:
                    logger.debug(
                        "Request: %s %s params=%s (attempt %d/%d)",
                        method,
                        url,
                        params,
                        attempt + 1,
                        self.max_retries + 1,
                    )

                    response = await self._http.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                    )
                    logger.debug(
                        "Response: status=%d, bytes=%d",
                        response.status_code,
                        len(response.content),
                    )
                    return await self._handle_response(response, url)

            except httpx.TimeoutException as e:
                logger.warning("Timeout: url=%s, timeout=%s", url, self.timeout)
                last_exception = OdynTimeoutError(
                    f"Request timed out after {self.timeout}s",
                    url=url,
                    timeout=self.timeout,
                    original_error=e,
                )

            except httpx.ConnectError as e:
                logger.warning("Connection failed: url=%s", url)
                last_exception = OdynConnectionError(
                    f"Failed to connect to {url}",
                    url=url,
                    original_error=e,
                )

            except Exception as e:
                if "SSL" in str(e) or "certificate" in str(e).lower():
                    logger.exception("SSL error: url=%s", url)
                    raise OdynSSLError(
                        f"SSL/TLS error: {e}",
                        url=url,
                        original_error=e,
                    ) from e

                # Check if this is a retryable Odyn exception
                if self._is_retryable(e):
                    last_exception = e
                else:
                    # Non-retryable exception, raise immediately
                    raise

            # If we get here, we have a retryable exception
            if attempt < self.max_retries:
                retry_after = None
                if isinstance(last_exception, RateLimitError):
                    retry_after = last_exception.retry_after

                backoff = self._calculate_backoff(attempt, retry_after)
                logger.info(
                    "Retrying request in %.2fs (attempt %d/%d): %s",
                    backoff,
                    attempt + 2,
                    self.max_retries + 1,
                    last_exception,
                )
                await asyncio.sleep(backoff)
            else:
                # All retries exhausted
                logger.error(
                    "All retry attempts exhausted (%d attempts): %s",
                    self.max_retries + 1,
                    last_exception,
                )
                raise RetryExhaustedError(
                    f"Request failed after {self.max_retries + 1} attempts",
                    attempts=self.max_retries + 1,
                    last_exception=last_exception,  # type: ignore[arg-type]
                ) from last_exception

        # This should never be reached, but type checker needs it
        raise RuntimeError("Unexpected exit from retry loop")  # pragma: no cover

    async def _fetch_page(
        self,
        url: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single page of results.

        Args:
            url: The URL to fetch.
            params: Optional query parameters.

        Returns:
            The parsed response containing 'value' array and optional '@odata.nextLink'.
        """
        return await self._request("GET", url, params=params)

    async def _paginate(
        self,
        url: str,
        params: dict[str, str] | None = None,
    ) -> pl.DataFrame:
        """Fetch all pages of results, following @odata.nextLink.

        Args:
            url: The initial URL to fetch.
            params: Optional query parameters for the first request.

        Returns:
            A Polars DataFrame containing all records from all pages.
        """
        frames: list[pl.DataFrame] = []
        current_url = url
        current_params = params
        page = 0

        while current_url and page < self.max_pages:
            data = await self._fetch_page(current_url, current_params)
            records = data.get("value", [])

            if records:
                frames.append(pl.DataFrame(records))
                logger.debug("Page %d: %d records", page + 1, len(records))

            next_link = data.get("@odata.nextLink")
            if next_link:
                current_url = next_link
                current_params = None  # nextLink includes all params
            else:
                break

            page += 1

        if page == self.max_pages:
            logger.warning(
                "Pagination limit reached: max_pages=%d, url=%s",
                self.max_pages,
                url,
            )

        if not frames:
            return pl.DataFrame()

        result = pl.concat(frames, how="diagonal_relaxed")
        logger.info("Fetched %d total records from %d pages", len(result), page + 1)
        return result

    async def _paginate_stream(
        self,
        url: str,
        params: dict[str, str] | None = None,
    ) -> AsyncIterator[pl.DataFrame]:
        """Stream pages of results as individual DataFrames.

        This is useful for processing large datasets page-by-page
        without loading everything into memory.

        Args:
            url: The initial URL to fetch.
            params: Optional query parameters for the first request.

        Yields:
            Polars DataFrame for each page of results.
        """
        current_url = url
        current_params = params
        page = 0

        while current_url and page < self.max_pages:
            data = await self._fetch_page(current_url, current_params)
            records = data.get("value", [])

            if records:
                logger.debug("Streaming page %d: %d records", page + 1, len(records))
                yield pl.DataFrame(records)

            next_link = data.get("@odata.nextLink")
            if next_link:
                current_url = next_link
                current_params = None
            else:
                break

            page += 1

    async def get(
        self,
        endpoint: str,
        *,
        query: ODataQuery | None = None,
        paginate: bool = True,
        use_cache: bool = True,
    ) -> pl.DataFrame:
        """Fetch data from a Business Central web service endpoint.

        Args:
            endpoint: OData entity set name (e.g., "customers", "salesOrders").
            query: Optional ODataQuery for filtering, sorting, etc.
            paginate: Whether to auto-fetch all pages (default: True).
            use_cache: Whether to use cache if available (default: True).

        Returns:
            Polars DataFrame with the results.

        Example:
            >>> # Simple query
            >>> df = await client.get("customers")
            >>>
            >>> # With filtering
            >>> from odyn.query import ODataQuery, F
            >>> query = (
            ...     ODataQuery().select("No", "Name", "Balance").filter(F.Balance > 1000).order_by("Name asc").top(50)
            ... )
            >>> df = await client.get("customers", query=query)
            >>>
            >>> # Force refresh (skip cache)
            >>> df = await client.get("customers", use_cache=False)
        """
        url = self._build_url(endpoint)
        params = query.build() if query else None

        logger.info("GET %s params=%s", endpoint, params)

        # Check cache
        cache_key = ""
        if self.cache and use_cache:
            cache_key = ParquetCache.make_key(url, params)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit: %s (%d rows)", endpoint, len(cached))
                return cached
            logger.debug("Cache miss: %s", endpoint)

        # Fetch from API
        if paginate:
            df = await self._paginate(url, params)
        else:
            data = await self._fetch_page(url, params)
            records = data.get("value", [])
            df = pl.DataFrame(records) if records else pl.DataFrame()

        # Store in cache
        if self.cache and use_cache and not df.is_empty():
            self.cache.set(cache_key, df, url=url, params=params)
            logger.debug("Cached: %s (%d rows)", endpoint, len(df))

        return df

    async def get_stream(
        self,
        endpoint: str,
        *,
        query: ODataQuery | None = None,
    ) -> AsyncIterator[pl.DataFrame]:
        """Stream data from an endpoint page by page.

        Unlike `get()`, this yields each page as a separate DataFrame,
        allowing processing of large datasets without loading everything
        into memory at once.

        Args:
            endpoint: OData entity set name.
            query: Optional ODataQuery for filtering, sorting, etc.

        Yields:
            Polars DataFrame for each page of results.

        Example:
            >>> async for page in client.get_stream("largeDataset"):
            ...     process_chunk(page)
        """
        url = self._build_url(endpoint)
        params = query.build() if query else None

        logger.info("GET STREAM %s params=%s", endpoint, params)

        async for page in self._paginate_stream(url, params):
            yield page

    async def get_by_key(
        self,
        endpoint: str,
        key: str,
        *,
        select: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single record by its primary key.

        Args:
            endpoint: OData entity set name (e.g., "customers").
            key: The primary key value (typically a string code like "C001").
            select: Optional list of fields to include.

        Returns:
            Dictionary with the record data.

        Example:
            >>> customer = await client.get_by_key("customers", "C001")
            >>> print(customer["Name"])
        """
        url = self._build_url(f"{endpoint}('{key}')")
        params: dict[str, str] = {}
        if select:
            params["$select"] = ",".join(select)

        logger.info("GET %s('%s')", endpoint, key)
        return await self._request("GET", url, params=params or None)

    async def get_by_id(
        self,
        endpoint: str,
        system_id: str,
        *,
        select: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single record by its SystemId (GUID).

        Args:
            endpoint: OData entity set name (e.g., "customers").
            system_id: The SystemId GUID.
            select: Optional list of fields to include.

        Returns:
            Dictionary with the record data.

        Example:
            >>> customer = await client.get_by_id("customers", "12345678-1234-1234-1234-123456789012")
        """
        url = self._build_url(f"{endpoint}({system_id})")
        params: dict[str, str] = {}
        if select:
            params["$select"] = ",".join(select)

        logger.info("GET %s(%s)", endpoint, system_id)
        return await self._request("GET", url, params=params or None)

    async def count(
        self,
        endpoint: str,
        *,
        query: ODataQuery | None = None,
    ) -> int:
        """Get the count of records in an endpoint.

        Args:
            endpoint: OData entity set name.
            query: Optional ODataQuery for filtering (only filter is used).

        Returns:
            Total number of matching records.

        Example:
            >>> total = await client.count("customers")
            >>> active = await client.count("customers", query=ODataQuery().filter(F.Status == "Active"))
        """
        url = self._build_url(f"{endpoint}/$count")
        params = query.build() if query else None

        # $count endpoint only respects $filter
        if params:
            params = {k: v for k, v in params.items() if k == "$filter"}

        logger.info("COUNT %s params=%s", endpoint, params)
        response_text = await self._request("GET", url, params=params or None)

        # $count returns plain text integer
        return int(response_text) if isinstance(response_text, str) else 0

    async def get_endpoints(self) -> list[str]:
        """Get list of available web service endpoints.

        Returns:
            List of endpoint names exposed by the OData service.

        Example:
            >>> endpoints = await client.get_endpoints()
            >>> print(endpoints)
            ['customers', 'vendors', 'items', ...]
        """
        logger.info("Fetching available endpoints")
        data = await self._request("GET", self.base_url)

        # OData service document format
        entities = data.get("value", [])
        return [entity.get("name", "") for entity in entities if entity.get("name")]

    async def close(self) -> None:
        """Close the HTTP client and release resources.

        This method is called automatically when using the client as
        an async context manager.
        """
        await self._http.aclose()
        logger.info("Client closed")

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        await self.close()

    # =========================================================================
    # Helper Methods - Convenience functions for common operations
    # =========================================================================

    async def get_first(
        self,
        endpoint: str,
        *,
        query: ODataQuery | None = None,
    ) -> dict[str, Any] | None:
        """Get the first record matching a query.

        Args:
            endpoint: OData entity set name.
            query: Optional ODataQuery for filtering.

        Returns:
            Dictionary with the first record, or None if no matches.

        Example:
            >>> customer = await client.get_first("customers", query=ODataQuery().filter(F.Name == "John"))
        """
        q = (query or ODataQuery()).top(1)
        df = await self.get(endpoint, query=q, paginate=False)
        if df.is_empty():
            return None
        return df.row(0, named=True)

    async def exists(
        self,
        endpoint: str,
        key: str,
    ) -> bool:
        """Check if a record exists by its primary key.

        Args:
            endpoint: OData entity set name.
            key: The primary key value.

        Returns:
            True if the record exists, False otherwise.

        Example:
            >>> if await client.exists("customers", "C001"):
            ...     print("Customer exists!")
        """
        try:
            await self.get_by_key(endpoint, key, select=["SystemId"])
        except NotFoundError:
            return False
        else:
            return True

    async def get_all(
        self,
        endpoint: str,
        *,
        batch_size: int = 1000,
    ) -> pl.DataFrame:
        """Get all records from an endpoint with optimized batching.

        This method fetches all records with a specified batch size
        for optimal performance.

        Args:
            endpoint: OData entity set name.
            batch_size: Number of records per page (default: 1000).

        Returns:
            Polars DataFrame with all records.

        Example:
            >>> all_customers = await client.get_all("customers")
        """
        query = ODataQuery().top(batch_size)
        return await self.get(endpoint, query=query)

    async def get_batch(
        self,
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
    ) -> pl.DataFrame:
        """Fetch records matching a list of values using concurrent batch requests.

        This method efficiently fetches records where a field matches any value
        in a large list. It automatically:
        - Chunks values into batches (default: 50 per batch)
        - Creates is_in() filters for each batch
        - Runs all requests concurrently (controlled by rate_limit and max_connections)
        - Combines results into a single DataFrame

        Args:
            endpoint: OData entity set name (e.g., "customers").
            field: Field name to filter on (e.g., "No" or "Customer_No").
            values: List of values to match (e.g., customer IDs).
            batch_size: Values per batch (default: 50). BC typically handles 50-100.
            select: Optional list of fields to return.
            expand: Optional list of related entities to include.
            order_by: Optional list of order clauses (e.g., ["Name asc"]).
            additional_filter: Optional additional filter expression to AND with is_in.
            fail_fast: If True, raise on first error. If False, continue and log errors.
            use_cache: Whether to use cached results (default: True).

        Returns:
            Polars DataFrame with all matching records from all batches.

        Raises:
            RetryExhaustedError: If fail_fast=True and a batch fails after retries.
            ValueError: If values list is empty.

        Example:
            >>> # Fetch 200 customers by ID, 50 at a time
            >>> customer_ids = ["C001", "C002", ..., "C200"]
            >>> customers = await client.get_batch(
            ...     "customers",
            ...     field="No",
            ...     values=customer_ids,
            ...     batch_size=50,
            ...     select=["No", "Name", "Balance_LCY"],
            ... )

            >>> # With additional filter
            >>> from odyn.query import F
            >>> active_customers = await client.get_batch(
            ...     "customers",
            ...     field="No",
            ...     values=customer_ids,
            ...     additional_filter=(F.Blocked == False),
            ... )
        """
        if not values:
            raise ValueError("values list cannot be empty")

        # Chunk values into batches
        batches = [values[i : i + batch_size] for i in range(0, len(values), batch_size)]

        logger.info(
            "Batch fetch: endpoint=%s, field=%s, total_values=%d, batches=%d, batch_size=%d",
            endpoint,
            field,
            len(values),
            len(batches),
            batch_size,
        )

        field_ref = Field(field)

        async def fetch_one_batch(batch_values: list[Any]) -> pl.DataFrame | None:
            """Fetch a single batch of values."""
            # Build query with is_in filter
            query = ODataQuery().filter(field_ref.is_in(batch_values))

            # Add additional filter if provided
            if additional_filter is not None:
                query = query.filter(additional_filter)

            # Add select, expand, order_by if provided
            if select:
                query = query.select(*select)
            if expand:
                query = query.expand(*expand)
            if order_by:
                query = query.order_by(*order_by)

            try:
                return await self.get(
                    endpoint,
                    query=query,
                    paginate=True,
                    use_cache=use_cache,
                )
            except Exception as e:
                if fail_fast:
                    raise
                logger.warning(
                    "Batch fetch failed for %d values: %s",
                    len(batch_values),
                    e,
                )
                return None

        # Run all batches concurrently
        # Rate limiting and semaphore are applied automatically in _request
        tasks = [fetch_one_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=not fail_fast)

        # Collect successful results
        frames: list[pl.DataFrame] = []
        errors = 0

        for result in results:
            if isinstance(result, BaseException):
                errors += 1
                logger.warning("Batch failed: %s", result)
            elif isinstance(result, pl.DataFrame) and not result.is_empty():
                frames.append(result)

        logger.info(
            "Batch fetch complete: %d successful, %d failed, %d total records",
            len(frames),
            errors,
            sum(len(f) for f in frames),
        )

        if not frames:
            return pl.DataFrame()

        return pl.concat(frames, how="diagonal_relaxed")

    def clear_cache(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries removed.

        Example:
            >>> removed = client.clear_cache()
            >>> print(f"Cleared {removed} entries")
        """
        if self.cache:
            count = self.cache.clear()
            logger.info("Cache cleared: %d entries removed", count)
            return count
        return 0

    def cleanup_cache(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of expired entries removed.

        Example:
            >>> removed = client.cleanup_cache()
            >>> print(f"Removed {removed} expired entries")
        """
        if self.cache:
            count = self.cache.cleanup()
            logger.info("Cache cleanup: %d expired entries removed", count)
            return count
        return 0

    @property
    def cache_size(self) -> int:
        """Get the number of cached entries.

        Returns:
            Number of entries in the cache, or 0 if no cache is configured.
        """
        return self.cache.size() if self.cache else 0

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        return (
            f"<BCWebServiceClient "
            f"base_url={self.base_url!r} "
            f"company={self.company!r} "
            f"cache={'enabled' if self.cache else 'disabled'}>"
        )
