# Getting Started

## Prerequisites

- **Python 3.12+**
- **Business Central on-premises** with OData Web Services enabled (the `/ODataV4` endpoint)
- Valid credentials (Basic auth username/password, or an API key)

### Business Central Setup

Odyn connects to Business Central's OData V4 endpoint at:

```
{server}/{instance}/ODataV4
```

For example: `https://bc-server:7048/BC210/ODataV4`

The web services you want to query must be published in Business Central under **Web Services** (Administration > Web Services). Each published page or query becomes an OData entity set (e.g., `customers`, `salesOrders`).

## Installation

```bash
pip install odyn
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add odyn
```

This installs Odyn and its three dependencies: `httpx`, `polars`, and `aiolimiter`.

## Your First Query

### Async (recommended)

```python
import asyncio
from odyn import BCWebServiceClient, BasicAuth

async def main():
    async with BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=BasicAuth("user", "password"),
        company="CRONUS International Ltd.",
    ) as client:
        df = await client.get("customers")
        print(df)
        print(f"Fetched {len(df)} customers")

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

### What happens

1. Odyn builds the URL: `https://bc-server:7048/BC210/ODataV4/Company('CRONUS International Ltd.')/customers`
2. Sends a GET request with Basic auth headers
3. Follows `@odata.nextLink` pagination automatically (up to 100 pages by default)
4. Converts the JSON response into a Polars DataFrame
5. Returns the DataFrame

## Adding Filters

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance_LCY")
    .filter(F.Balance_LCY > 1000)
    .order_by("Name asc")
    .top(50)
)

df = await client.get("customers", query=query)
```

This generates:

```
$select=No,Name,Balance_LCY&$filter=Balance_LCY gt 1000&$orderby=Name asc&$top=50
```

## Self-Signed Certificates

BC on-premises often uses self-signed SSL certificates. Disable verification:

```python
client = BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    verify_ssl=False,
)
```

## Domain Authentication

For Windows domain auth, use the `DOMAIN\user` format:

```python
auth = BasicAuth("MYDOMAIN\\svc_account", "password")
```

## Next Steps

- [Client Configuration](client.md) — all parameters for `BCWebServiceClient.create()`
- [Authentication](auth.md) — BasicAuth and APIKeyAuth options
- [Query Builder](query.md) — the full filter expression DSL
- [Caching](cache.md) — enable Parquet caching for repeated queries
