import asyncio

from odyn import BasicAuth, BCWebServiceClient


def on_progress(*, page, records_on_page, total_records, is_final):
    """Progress callback for monitoring pagination."""
    status = "Complete" if is_final else "In progress"
    print(f"Page {page}: {records_on_page} records ({total_records} total) - {status}")


async def main():
    async with BCWebServiceClient.create(...) as client:
        # For extremely large datasets (millions of rows), use get_stream
        # to process data page-by-page without loading everything into memory.

        row_count = 0
        async for page_df in client.get_stream("ItemLedgerEntries", on_progress=on_progress):
            # page_df is a Polars DataFrame for a single OData page
            row_count += len(page_df)

            # Perform page-level processing
            # page_df.write_parquet(f"chunk_{row_count}.parquet")

        print(f"Total rows processed: {row_count}")

        # Progress callbacks also work with get() for auto-pagination
        df = await client.get("customers", on_progress=on_progress)
        print(f"Fetched {len(df)} customers")


if __name__ == "__main__":
    asyncio.run(main())
