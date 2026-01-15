# Odyn Examples

Small, functional examples demonstrating the capabilities of the Odyn client. These are designed for reading and comprehension.

| Example | Description |
|---------|-------------|
| [01_quickstart.py](01_quickstart.py) | Basic setup and simple GET request |
| [02_query_builder.py](02_query_builder.py) | Filtering, selection, ordering, and expands |
| [03_lookups.py](03_lookups.py) | Fetching single records by key or ID |
| [04_batch_operations.py](04_batch_operations.py) | Concurrent lookups for multiple IDs with progress tracking |
| [05_streaming.py](05_streaming.py) | Processing large datasets page-by-page with progress callbacks |
| [06_caching.py](06_caching.py) | Persistent Parquet-based caching with statistics |
| [07_error_handling.py](07_error_handling.py) | Common exceptions and error patterns |
| [08_configuration.py](08_configuration.py) | Advanced client settings (retries, rate limits, hooks) |
| [09_sync_compatibility.py](09_sync_compatibility.py) | Using `BCWebServiceClientSync` in non-async applications |
| [10_metadata.py](10_metadata.py) | Inspecting available endpoints and counts |

## Key Features Demonstrated

- **Progress Callbacks**: Monitor pagination and batch operations (see 04, 05)
- **Cache Statistics**: Track hits, misses, and disk usage (see 06)
- **Sync Client**: Use `BCWebServiceClientSync` for scripts and notebooks (see 09)

## Notes for Developers

- **Async First**: Odyn is built on `httpx` and `asyncio`. Use the `async with` context manager to ensure connections are properly pooled and closed. For non-async contexts, use `BCWebServiceClientSync`.
- **Polars Integration**: Most methods return Polars DataFrames for high-performance data manipulation.
- **Mock Config**: Example files use placeholder URLs and credentials. Update these with your Business Central server details for local testing.
