# Odyn

Async-first Python client for Microsoft Dynamics 365 Business Central on-premises OData Web Services. Returns native Polars DataFrames with built-in caching, rate limiting, retry logic, and a fluent query builder.

> **Scope:** Odyn targets Business Central **OData Web Services** only. It is not designed for the standard Business Central API v2.0 endpoints.

## Why Odyn

Integrating with Business Central Web Services means dealing with NTLM/Basic auth, manual OData query strings, pagination loops, and converting JSON blobs into something useful. Odyn handles all of that behind a single async call that returns a Polars DataFrame.

- **Async + sync** — built on httpx; sync wrapper included for scripts and notebooks
- **Polars DataFrames** — columnar, fast, zero-copy where possible
- **Fluent query builder** — type-safe filters via the `F` singleton, method chaining, raw escape hatch
- **Parquet caching** — local file cache with TTL, SHA256 keys, hit/miss stats
- **Resilience** — exponential backoff with jitter, rate limiting via token bucket, concurrency control
- **Batch operations** — concurrent chunked lookups with progress callbacks
- **Delta sync** — `get_since()` / `get_before()` for incremental loads
- **Streaming** — page-by-page async iteration for large datasets
- **Hooks** — plug in request/response observers for logging, metrics, or tracing

## Requirements

- Python 3.12+
- httpx >= 0.28
- polars >= 1.36
- aiolimiter >= 1.2

## Installation

```bash
pip install odyn
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add odyn
```

## Quick Start

### Async

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth
from odyn.query import ODataQuery, F

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("DOMAIN\\user", "password"),
        company="CRONUS International Ltd.",
    ) as client:
        # All customers as a Polars DataFrame
        customers = await client.get("customers")

        # Filtered query
        query = (
            ODataQuery()
            .select("No", "Name", "Balance_LCY")
            .filter(F.Balance_LCY > 1000)
            .filter(F.Blocked == False)
            .order_by("Balance_LCY desc")
            .top(50)
        )
        top_customers = await client.get("customers", query=query)

        # Single record by key
        customer = await client.get_by_key("customers", "C00010")

asyncio.run(main())
```

### Sync

```python
from odyn import BCWebServiceClientSync, BasicAuth

with BCWebServiceClientSync.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    company="CRONUS",
) as client:
    df = client.get("customers")
    print(df)
```

### API Key Authentication

```python
from odyn import BCWebServiceClient, APIKeyAuth

auth = APIKeyAuth("my-secret-api-key")

# Or with a custom header
auth = APIKeyAuth("my-key", header_name="X-API-Key", prefix="")
```

## Query Builder

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY")
    .filter(F.Status == "Active")          # eq
    .filter(F.Balance_LCY > 1000)          # gt
    .filter(F.Type.is_in(["Customer", "Vendor"]))  # IN via OR chain
    .expand("SalesLines")
    .order_by("Name asc")
    .top(100)
    .skip(50)
)

# Raw OData for functions not covered by the DSL
query = ODataQuery().filter_raw("contains(Name, 'Corp')")

# Combine expressions with & and |
expr = (F.Status == "Active") & (F.Balance_LCY > 0)
expr = (F.City == "London") | (F.City == "Berlin")
```

## Caching

```python
async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
    cache_dir="~/.cache/odyn",
    cache_ttl=3600,  # 1 hour
) as client:
    df = await client.get("customers")                   # cache miss — fetches from API
    df = await client.get("customers")                   # cache hit — reads Parquet
    df = await client.get("customers", use_cache=False)  # force refresh

    client.cleanup_cache()  # remove expired entries
```

## Batch Operations

```python
customer_ids = ["C001", "C002", ..., "C500"]

df = await client.get_batch(
    "customers",
    field="No",
    values=customer_ids,
    batch_size=50,
    select=["No", "Name", "Balance_LCY"],
)
```

## Delta Sync

```python
from datetime import datetime, timedelta, timezone

since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
updated = await client.get_since("customers", since)
```

## Streaming

```python
async for page in client.get_stream("largeDataset"):
    process(page)  # each page is a Polars DataFrame
```

## Documentation

Full documentation lives in [docs/](docs/index.md):

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, prerequisites, first connection |
| [Client](docs/client.md) | Creating and configuring the client |
| [Authentication](docs/auth.md) | BasicAuth, APIKeyAuth, custom headers |
| [Query Builder](docs/query.md) | Filters, select, expand, order, the F singleton |
| [Caching](docs/cache.md) | ParquetCache, TTL, cache management |
| [Sync Client](docs/sync.md) | Synchronous wrapper for non-async contexts |
| [Advanced](docs/advanced.md) | Hooks, streaming, batch ops, delta sync, concurrency |
| [Exceptions](docs/exceptions.md) | Exception hierarchy and error handling |
| [API Reference](docs/api.md) | Every class, method, parameter, and type |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [LLM Context](docs/llm-context.md) | Single-file complete reference for AI assistants |

## License

[MIT](LICENSE)
