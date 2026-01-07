import asyncio

from odyn import BasicAuth, BCWebServiceClient


async def main():
    async with BCWebServiceClient.create(...) as client:
        # For extremely large datasets (millions of rows), use get_stream
        # to process data page-by-page without loading everything into memory.

        row_count = 0
        async for page_df in client.get_stream("ItemLedgerEntries"):
            # page_df is a Polars DataFrame for a single OData page
            row_count += len(page_df)

            # Perform page-level processing
            # page_df.write_parquet(f"chunk_{row_count}.parquet")

        print(f"Total rows processed: {row_count}")


if __name__ == "__main__":
    asyncio.run(main())
