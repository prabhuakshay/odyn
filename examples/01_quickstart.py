import asyncio

import polars as pl

from odyn import BasicAuth, BCWebServiceClient


async def main():
    # The client uses an async context manager for automatic resource cleanup
    async with BCWebServiceClient.create(
        server="https://bc-server.example.com:7048",
        instance="BC240",
        company="CRONUS International Ltd.",
        auth=BasicAuth("DOMAIN\\user", "password"),
    ) as client:
        # Fetch all records from an endpoint (returns a Polars DataFrame)
        customers = await client.get("customers")

        # BC result sets are returned as Polars DataFrames for efficient processing
        print(customers.select("No", "Name", "Balance").head())


if __name__ == "__main__":
    asyncio.run(main())
