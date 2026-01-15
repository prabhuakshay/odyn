"""Synchronous wrapper for the async Business Central client.

This module provides a synchronous interface to the BCWebServiceClient
for use in non-async contexts. It runs async operations in a background
thread with its own event loop.

Example:
    >>> from odyn.sync import BCWebServiceClientSync
    >>> from odyn import BasicAuth
    >>>
    >>> with BCWebServiceClientSync.create(
    ...     server="https://bc-server:7048",
    ...     instance="BC210",
    ...     auth=BasicAuth("user", "pass"),
    ... ) as client:
    ...     customers = client.get("customers")
    ...     print(f"Found {len(customers)} customers")
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

from odyn.client import (
    BatchProgressCallback,
    BCWebServiceClient,
    ProgressCallback,
    RequestHook,
    ResponseHook,
)

if TYPE_CHECKING:
    from pathlib import Path

    import polars as pl

    from odyn.auth import BasicAuth
    from odyn.query import ODataQuery
    from odyn.query.expressions import FilterExpression

__all__ = ["BCWebServiceClientSync"]

logger = logging.getLogger("odyn.sync")


class BCWebServiceClientSync:
    """Synchronous wrapper for BCWebServiceClient.

    This class provides a blocking interface to the async client by
    running async operations in a background thread with its own event loop.

    All methods mirror the async client but block until completion.

    Attributes:
        _client: The wrapped async BCWebServiceClient instance.

    Example:
        >>> with BCWebServiceClientSync.create(
        ...     server="https://bc-server:7048",
        ...     instance="BC210",
        ...     auth=BasicAuth("user", "pass"),
        ... ) as client:
        ...     df = client.get("customers")
    """

    __slots__ = ("_client", "_loop", "_thread")

    def __init__(self, client: BCWebServiceClient) -> None:
        """Initialize with an existing async client.

        Args:
            client: The async BCWebServiceClient to wrap.
        """
        self._client = client
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def _start_background_loop(self) -> None:
        """Start the background event loop thread."""
        if self._loop is not None and self._loop.is_running():
            return

        self._loop = asyncio.new_event_loop()

        def run_loop() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

    def _run(self, coro: Any) -> Any:
        """Run a coroutine in the background event loop.

        Args:
            coro: The coroutine to run.

        Returns:
            The result of the coroutine.
        """
        self._start_background_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)  # type: ignore[arg-type]
        return future.result()

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
        max_connections: int = 4,
        requests_per_minute: float | None = 550.0,
        max_burst: int | None = None,
        on_request: RequestHook | None = None,
        on_response: ResponseHook | None = None,
    ) -> BCWebServiceClientSync:
        r"""Create a synchronous client for Business Central web services.

        This is the recommended factory method for creating a sync client.
        All parameters match BCWebServiceClient.create().

        Args:
            server: Server URL (e.g., "https://bc-server:7048").
            instance: BC instance name (e.g., "BC210").
            auth: Authentication strategy (BasicAuth).
            company: Optional company name to scope all requests.
            timeout: Request timeout in seconds (default: 30).
            max_pages: Maximum pages to fetch during auto-pagination (default: 100).
            verify_ssl: Whether to verify SSL certificates (default: True).
            cache_dir: Optional directory for Parquet cache.
            cache_ttl: Optional cache TTL in seconds.
            log_level: Logging level (default: INFO).
            max_retries: Maximum retry attempts for transient failures (default: 3).
            retry_backoff: Base delay for exponential backoff (default: 1.0).
            max_connections: Maximum concurrent connections (default: 4).
            requests_per_minute: Maximum requests per minute (default: 550).
            max_burst: Maximum burst size for rate limiting (default: max_connections).
            on_request: Optional hook called before each HTTP request.
            on_response: Optional hook called after each HTTP response.

        Returns:
            Configured BCWebServiceClientSync instance.

        Example:
            >>> client = BCWebServiceClientSync.create(
            ...     server="https://bc-server:7048",
            ...     instance="BC210",
            ...     auth=BasicAuth("DOMAIN\\user", "password"),
            ...     company="CRONUS International Ltd.",
            ... )
        """
        async_client = BCWebServiceClient.create(
            server=server,
            instance=instance,
            auth=auth,
            company=company,
            timeout=timeout,
            max_pages=max_pages,
            verify_ssl=verify_ssl,
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            log_level=log_level,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            max_connections=max_connections,
            requests_per_minute=requests_per_minute,
            max_burst=max_burst,
            on_request=on_request,
            on_response=on_response,
        )
        return cls(async_client)

    def get(
        self,
        endpoint: str,
        *,
        query: ODataQuery | None = None,
        paginate: bool = True,
        use_cache: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> pl.DataFrame:
        """Fetch data from a Business Central web service endpoint.

        Args:
            endpoint: OData entity set name (e.g., "customers").
            query: Optional ODataQuery for filtering, sorting, etc.
            paginate: Whether to auto-fetch all pages (default: True).
            use_cache: Whether to use cache if available (default: True).
            on_progress: Optional callback invoked after each page is fetched.

        Returns:
            Polars DataFrame with the results.
        """
        return self._run(
            self._client.get(
                endpoint,
                query=query,
                paginate=paginate,
                use_cache=use_cache,
                on_progress=on_progress,
            )
        )

    def get_by_key(
        self,
        endpoint: str,
        key: str,
        *,
        select: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single record by its primary key.

        Args:
            endpoint: OData entity set name.
            key: The primary key value.
            select: Optional list of fields to include.

        Returns:
            Dictionary with the record data.
        """
        return self._run(self._client.get_by_key(endpoint, key, select=select))

    def get_by_id(
        self,
        endpoint: str,
        system_id: str,
        *,
        select: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a single record by its SystemId (GUID).

        Args:
            endpoint: OData entity set name.
            system_id: The SystemId GUID.
            select: Optional list of fields to include.

        Returns:
            Dictionary with the record data.
        """
        return self._run(self._client.get_by_id(endpoint, system_id, select=select))

    def count(
        self,
        endpoint: str,
        *,
        query: ODataQuery | None = None,
    ) -> int:
        """Get the count of records in an endpoint.

        Args:
            endpoint: OData entity set name.
            query: Optional ODataQuery for filtering.

        Returns:
            Total number of matching records.
        """
        return self._run(self._client.count(endpoint, query=query))

    def get_endpoints(self) -> list[str]:
        """Get list of available web service endpoints.

        Returns:
            List of endpoint names.
        """
        return self._run(self._client.get_endpoints())

    def get_first(
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
        """
        return self._run(self._client.get_first(endpoint, query=query))

    def exists(
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
        """
        return self._run(self._client.exists(endpoint, key))

    def get_since(
        self,
        endpoint: str,
        timestamp: str,
        *,
        query: ODataQuery | None = None,
        use_cache: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> pl.DataFrame:
        """Get records modified since a timestamp (delta sync).

        Args:
            endpoint: OData entity set name.
            timestamp: ISO 8601 timestamp.
            query: Optional additional ODataQuery.
            use_cache: Whether to cache results (default: False).
            on_progress: Optional callback invoked after each page.

        Returns:
            Polars DataFrame with records modified after the timestamp.
        """
        return self._run(
            self._client.get_since(
                endpoint,
                timestamp,
                query=query,
                use_cache=use_cache,
                on_progress=on_progress,
            )
        )

    def get_before(
        self,
        endpoint: str,
        timestamp: str,
        *,
        query: ODataQuery | None = None,
        use_cache: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> pl.DataFrame:
        """Get records modified before a timestamp.

        Args:
            endpoint: OData entity set name.
            timestamp: ISO 8601 timestamp.
            query: Optional additional ODataQuery.
            use_cache: Whether to cache results (default: True).
            on_progress: Optional callback invoked after each page.

        Returns:
            Polars DataFrame with records modified before the timestamp.
        """
        return self._run(
            self._client.get_before(
                endpoint,
                timestamp,
                query=query,
                use_cache=use_cache,
                on_progress=on_progress,
            )
        )

    def get_all(
        self,
        endpoint: str,
        *,
        batch_size: int = 1000,
    ) -> pl.DataFrame:
        """Get all records from an endpoint with optimized batching.

        Args:
            endpoint: OData entity set name.
            batch_size: Number of records per page (default: 1000).

        Returns:
            Polars DataFrame with all records.
        """
        return self._run(self._client.get_all(endpoint, batch_size=batch_size))

    def get_batch(
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
        on_progress: BatchProgressCallback | None = None,
    ) -> pl.DataFrame:
        """Fetch records matching a list of values using batch requests.

        Args:
            endpoint: OData entity set name.
            field: Field name to filter on.
            values: List of values to match.
            batch_size: Values per batch (default: 50).
            select: Optional list of fields to return.
            expand: Optional list of related entities to include.
            order_by: Optional list of order clauses.
            additional_filter: Optional additional filter expression.
            fail_fast: If True, raise on first error.
            use_cache: Whether to use cached results (default: True).
            on_progress: Optional callback invoked after each batch.

        Returns:
            Polars DataFrame with all matching records.
        """
        return self._run(
            self._client.get_batch(
                endpoint,
                field,
                values,
                batch_size=batch_size,
                select=select,
                expand=expand,
                order_by=order_by,
                additional_filter=additional_filter,
                fail_fast=fail_fast,
                use_cache=use_cache,
                on_progress=on_progress,
            )
        )

    def clear_cache(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries removed.
        """
        return self._client.clear_cache()

    def cleanup_cache(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of expired entries removed.
        """
        return self._client.cleanup_cache()

    @property
    def cache_size(self) -> int:
        """Get the number of cached entries."""
        return self._client.cache_size

    @property
    def cache_stats(self) -> dict[str, int] | None:
        """Get cache statistics."""
        return self._client.cache_stats

    def close(self) -> None:
        """Close the client and release resources."""
        if self._loop is not None and self._loop.is_running():
            # Close the async client first
            self._run(self._client.close())
            # Stop and close the event loop
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5.0)
            # Close the loop to release resources
            self._loop.close()
            self._loop = None
            self._thread = None
        logger.info("Sync client closed")

    def __enter__(self) -> BCWebServiceClientSync:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        self.close()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<BCWebServiceClientSync wrapping {self._client!r}>"
