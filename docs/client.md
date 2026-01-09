# Client Guide

The `BCWebServiceClient` is the central component of Odyn. It manages the lifecycle of HTTP connections, handles authentication, provides automatic retry logic, and manages the caching of responses.

## Initialization

The recommended way to initialize the client is using the `create()` factory method. This ensures that all components, including the internal `httpx.AsyncClient`, are properly configured.

```python
from odyn import BCWebServiceClient, BasicAuth

client = BCWebServiceClient.create(
    server="https://bc.example.com",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    company="CRONUS",
)
```

## Lifecycle Management

### As a Context Manager

Using the client as an async context manager is the safest way to ensure that resources are cleaned up immediately after use.

```python
async with BCWebServiceClient.create(...) as client:
    data = await client.get("customers")
# Client is closed here
```

### Manual Management

In long-running scripts or applications where the client instance is shared (e.g., in a data pipeline), you can manage the lifecycle manually.

```python
client = BCWebServiceClient.create(...)

# ... perform requests ...

await client.close()
```

## Fetching Data

### DataFrames

The `get()` method is the primary way to fetch data. It returns a `polars.DataFrame`, which is highly efficient for data manipulation. Odyn handles the conversion from the OData JSON response to the DataFrame schema automatically.

### Auto-Pagination

By default, `get()` will follow `@odata.nextLink` pointers until all data has been fetched (up to `max_pages`). This allows you to fetch large datasets with a single method call without worrying about pagination logic.

### Streaming

For extremely large datasets that might not fit comfortably in memory, use `get_stream()`. This yields one DataFrame per page of results, allowing you to process data incrementally.

## Resilience Features

Odyn includes built-in features to make your integrations more robust:

1. **Retries**: Automatically retries requests that fail due to network timeouts, connection issues, or transient server errors (5xx). It uses exponential backoff to avoid hammering the server.
2. **Rate Limiting**: Throttles outgoing requests using aiolimiter (token bucket algorithm) to a specified number of requests per minute (RPM) to comply with server-side throughput limits. Default is 550 requests per minute.
3. **Concurrency Control**: Limits the number of concurrent outgoing requests to prevent overwhelming the Business Central instance and to manage connection pooling efficiently.

## Advanced Fetching

### Efficient Batching (`get_batch`)

Standard OData filters are restricted by URL length limits. If you need to fetch records matching a large list of IDs (e.g., 500 customer numbers), a single filter string would be too long.

`client.get_batch()` solves this by:
1. Chunks the input list into smaller groups (default 50).
2. Executes requests concurrently (respecting `max_connections`).
3. Merges all returned data into a single Polars DataFrame.

```python
customers = await client.get_batch(
    endpoint="customers",
    field="No",
    values=large_id_list
)
```
