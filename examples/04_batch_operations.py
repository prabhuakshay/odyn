import asyncio

from odyn import BasicAuth, BCWebServiceClient


async def main():
    async with BCWebServiceClient.create(...) as client:
        # Batch Fetching
        # When you have a long list of IDs (e.g., 500 customer numbers),
        # get_batch automatically chunks them into OData 'or' filters
        # and runs requests concurrently for maximum throughput.

        customer_nos = [f"C{i:05d}" for i in range(1, 501)]

        customers = await client.get_batch(
            endpoint="customers", field="No", values=customer_nos, select=["No", "Name", "Post_Code"]
        )

        # 'customers' is a single Polars DataFrame containing all matches
        print(f"Retrieved {len(customers)} records")


if __name__ == "__main__":
    asyncio.run(main())
