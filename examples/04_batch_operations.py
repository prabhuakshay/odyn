import asyncio

from odyn import BasicAuth, BCWebServiceClient


def on_batch_progress(*, batch, total_batches, successful, failed, is_final):
    """Progress callback for monitoring batch operations."""
    status = "Complete" if is_final else "In progress"
    print(f"Batch {batch}/{total_batches}: {successful} ok, {failed} failed - {status}")


async def main():
    async with BCWebServiceClient.create(...) as client:
        # Batch Fetching
        # When you have a long list of IDs (e.g., 500 customer numbers),
        # get_batch automatically chunks them into OData 'or' filters
        # and runs requests concurrently for maximum throughput.

        customer_nos = [f"C{i:05d}" for i in range(1, 501)]

        customers = await client.get_batch(
            endpoint="customers",
            field="No",
            values=customer_nos,
            select=["No", "Name", "Post_Code"],
            on_progress=on_batch_progress,  # Monitor batch progress
        )

        # 'customers' is a single Polars DataFrame containing all matches
        print(f"Retrieved {len(customers)} records")


if __name__ == "__main__":
    asyncio.run(main())
