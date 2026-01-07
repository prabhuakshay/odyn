import asyncio
import logging

from odyn import BasicAuth, BCWebServiceClient


async def main():
    # Advanced client configuration for production environments
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC240",
        auth=BasicAuth("user", "pass"),
        # Connection settings
        verify_ssl=True,  # Use False only for dev with self-signed certs
        timeout=60.0,  # Total request timeout
        max_connections=10,  # Maximum concurrent connections
        # Reliability
        max_retries=5,  # Retries for 429, 5xx, and timeouts
        retry_backoff=2.0,  # Base for exponential backoff (2, 4, 8, 16...)
        rate_limit=5.0,  # Max requests per second
        # Behavior
        max_pages=1000,  # Safety cap for auto-pagination
        log_level=logging.INFO,  # Odyn uses structured logging
    ) as client:
        await client.get("customers")


if __name__ == "__main__":
    asyncio.run(main())
