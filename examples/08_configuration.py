import asyncio
import logging

from odyn import BasicAuth, BCWebServiceClient


def log_request(*, method, url, params):  # noqa: ARG001
    """Called before each HTTP request."""
    print(f">> {method} {url}")


def log_response(*, method, url, status_code, duration_ms):  # noqa: ARG001
    """Called after each HTTP response."""
    print(f"<< {status_code} in {duration_ms:.0f}ms")


async def main():
    # Advanced client configuration for production environments
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC240",
        auth=BasicAuth("user", "pass"),
        # Connection settings
        verify_ssl=True,  # Use False only for dev with self-signed certs
        timeout=60.0,  # Total request timeout
        max_connections=4,  # Maximum concurrent connections (default: 4)
        # Reliability
        max_retries=5,  # Retries for 429, 5xx, and timeouts
        retry_backoff=2.0,  # Base for exponential backoff (2, 4, 8, 16...)
        requests_per_minute=300.0,  # Max requests per minute (default: 550)
        max_burst=4,  # Max burst size, prevents hammering on startup
        # Behavior
        max_pages=1000,  # Safety cap for auto-pagination
        log_level=logging.INFO,  # Odyn uses structured logging
        # Hooks for logging/metrics
        on_request=log_request,
        on_response=log_response,
    ) as client:
        await client.get("customers")


if __name__ == "__main__":
    asyncio.run(main())
