# Odyn

Odyn is a modern, async-first Python client for Microsoft Dynamics 365 Business Central Web Services. It provides a high-level interface for extracting and interacting with data from Business Central using OData, handling the complexities of authentication, rate limiting, and data transformation.

## Project Scope

This project was designed for personal use and follows an opinionated structure. It currently supports Business Central **OData Web Services** specifically. It is not intended for use with the standard Business Central API v2.0 endpoints.

## Problem Solved

Integrating with Business Central Web Services often involves significant boilerplate for authentication, manual construction of OData queries, complex pagination logic, and data conversion. Odyn eliminates this overhead by providing a type-safe, fluent API that returns native Polars DataFrames, designed specifically for data engineering and high-performance integration tasks.

## Capabilities

* Async Execution: Built on httpx for high-performance asynchronous I/O.
* Polars Integration: Native support for Polars DataFrames for efficient data processing.
* Query Builder: Type-safe OData query builder with support for filters, expansions, and ordering.
* Caching: Persistent Parquet-based caching with configurable TTL to reduce API load.
* Resilience: Automatic retries with exponential backoff and configurable rate limiting.
* Data Handling: Automatic pagination, streaming, and efficient batching for large datasets.

## Dependencies

* Python 3.12+
* httpx
* polars

## Installation

```bash
pip install odyn
```

## Quick Example

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth
from odyn.query import ODataQuery, F

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC200",
        auth=BasicAuth("user", "password"),
        company="CRONUS",
    ) as client:
        # Fetch customers with balance > 1000
        query = ODataQuery().filter(F.Balance > 1000)
        df = await client.get("customers", query=query)
        print(df)

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation

Comprehensive documentation is available in the [docs/](docs/index.md) directory:

* [API Reference](docs/api.md) — Detailed class and method reference.
* [Client Configuration](docs/client.md) — Setting up the `BCWebServiceClient`.
* [Authentication](docs/auth.md) — Configuring authentication for your environment.
* [Query Builder](docs/query.md) — Building type-safe filters and expansions.
* [Caching](docs/cache.md) — Improving performance with local Parquet caching.
* [Exception Handling](docs/exceptions.md) — Understanding the error hierarchy.
* [Troubleshooting](docs/troubleshooting.md) — Solutions for common BC integration issues.

## Examples

Refer to the [examples/](examples/) directory for functional examples covering various use cases:

* **[Quickstart](examples/01_quickstart.py)**: Basic setup and simple GET request.
* **[Query Builder](examples/02_query_builder.py)**: Filtering, selection, ordering, and expands.
* **[Lookups](examples/03_lookups.py)**: Fetching single records by key or ID.
* **[Batch Operations](examples/04_batch_operations.py)**: Concurrent lookups for multiple IDs.
* **[Streaming](examples/05_streaming.py)**: Processing large datasets page-by-page.
* **[Caching](examples/06_caching.py)**: Persistent Parquet-based caching.
* **[Error Handling](examples/07_error_handling.py)**: Common exceptions and error patterns.
* **[Configuration](examples/08_configuration.py)**: Advanced client settings (retries, rate limits).
* **[Sync Compatibility](examples/09_sync_compatibility.py)**: Using Odyn in non-async applications.
* **[Metadata](examples/10_metadata.py)**: Inspecting available endpoints and counts.

## License

[MIT](LICENSE)
