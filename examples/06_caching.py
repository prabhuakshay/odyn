import asyncio
from pathlib import Path

from odyn import BasicAuth, BCWebServiceClient


async def main():
    # Odyn supports persistent caching of results as Parquet files.
    # This is ideal for static master data (Customers, Items, etc.)
    # to avoid hitting the BC server repeatedly.

    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC240",
        auth=BasicAuth("user", "pass"),
        cache_dir="./.odyn_cache",
        cache_ttl=3600,  # 1 hour
    ) as client:
        # First call: Fetch from BC, save to ./.odyn_cache/*.parquet
        df1 = await client.get("customers")

        # Second call: Load instantly from local disk
        df2 = await client.get("customers")

        # Force a fresh fetch from the server
        df3 = await client.get("customers", use_cache=False)

        # Check cache statistics
        stats = client.cache_stats
        if stats:
            print(f"Cache hits: {stats['hits']}")
            print(f"Cache misses: {stats['misses']}")
            print(f"Disk usage: {stats['disk_bytes'] / 1024:.1f} KB")

        # Check number of cached entries
        print(f"Entries in cache: {client.cache_size}")

        # Clean up expired entries
        removed = client.cleanup_cache()
        print(f"Removed {removed} expired entries")


if __name__ == "__main__":
    asyncio.run(main())
