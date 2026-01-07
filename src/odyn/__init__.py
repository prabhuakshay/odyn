r"""Odyn - Python client for Business Central Web Services API.

Odyn provides a modern, async-first client for interacting with
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
    - Fluent OData query builder with expression DSL

Quick Start:
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
    ...     query = ODataQuery().filter(F.Balance > 1000).order_by("Name asc").top(10)
    ...     top_customers = await client.get("customers", query=query)

Authentication:
    >>> from odyn import BasicAuth
    >>> auth = BasicAuth("DOMAIN\\\\user", "password")

Caching:
    >>> from odyn import ParquetCache
    >>> from pathlib import Path
    >>>
    >>> cache = ParquetCache(Path("~/.cache/odyn").expanduser(), default_ttl=3600)

Query Building:
    >>> from odyn.query import ODataQuery, F
    >>>
    >>> query = (
    ...     ODataQuery()
    ...     .select("No", "Name", "Balance")
    ...     .filter(F.Status == "Active")
    ...     .filter(F.Balance > 0)
    ...     .expand("SalesLines")
    ...     .order_by("Name asc")
    ...     .top(100)
    ...     .skip(50)
    ... )
"""

from odyn.auth import BasicAuth
from odyn.cache import CacheMetadata, ParquetCache
from odyn.client import BCWebServiceClient
from odyn.exceptions import (
    AuthenticationError,
    ConnectionError as OdynConnectionError,
    ForbiddenError,
    NotFoundError,
    OdynError,
    QueryValidationError,
    RateLimitError,
    RetryExhaustedError,
    ServerError,
    SSLError as OdynSSLError,
    TimeoutError as OdynTimeoutError,
    ValidationError,
    WebServiceError,
)

__all__ = [
    "AuthenticationError",
    "BCWebServiceClient",
    "BasicAuth",
    "CacheMetadata",
    "ForbiddenError",
    "NotFoundError",
    "OdynConnectionError",
    "OdynError",
    "OdynSSLError",
    "OdynTimeoutError",
    "ParquetCache",
    "QueryValidationError",
    "RateLimitError",
    "RetryExhaustedError",
    "ServerError",
    "ValidationError",
    "WebServiceError",
]

__version__ = "0.1.0"
