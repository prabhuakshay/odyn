# Odyn Examples

Small, functional examples demonstrating the capabilities of the Odyn client. These are designed for reading and comprehension.

| Example | Description |
|---------|-------------|
| [01_quickstart.py](01_quickstart.py) | Basic setup and simple GET request |
| [02_query_builder.py](02_query_builder.py) | Filtering, selection, ordering, and expands |
| [03_lookups.py](03_lookups.py) | Fetching single records by key or ID |
| [04_batch_operations.py](04_batch_operations.py) | Concurrent lookups for multiple IDs |
| [05_streaming.py](05_streaming.py) | Processing large datasets page-by-page |
| [06_caching.py](06_caching.py) | Persistent Parquet-based caching |
| [07_error_handling.py](07_error_handling.py) | Common exceptions and error patterns |
| [08_configuration.py](08_configuration.py) | Advanced client settings (retries, rate limits) |
| [09_sync_compatibility.py](09_sync_compatibility.py) | Using Odyn in non-async applications |
| [10_metadata.py](10_metadata.py) | Inspecting available endpoints and counts |

## Notes for Developers

- **Async First**: Odyn is built on `httpx` and `asyncio`. Use the `async with` context manager to ensure connections are properly pooled and closed.
- **Polars Integration**: Most methods return Polars DataFrames for high-performance data manipulation.
- **Mock Config**: Example files use placeholder URLs and credentials. Update these with your Business Central server details for local testing.
