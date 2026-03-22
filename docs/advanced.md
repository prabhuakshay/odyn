# Advanced Usage

This guide covers hooks, streaming, batch operations, delta sync, and concurrency tuning.

## Request & Response Hooks

Hooks let you observe every HTTP request and response — useful for logging, metrics, tracing, or debugging.

### RequestHook

Called before each HTTP request is sent.

```python
def on_request(*, method: str, url: str, params: dict[str, str] | None) -> None:
    print(f">>> {method} {url}")
```

### ResponseHook

Called after each HTTP response is received.

```python
def on_response(*, method: str, url: str, status_code: int, duration_ms: float) -> None:
    print(f"<<< {status_code} {url} ({duration_ms:.0f}ms)")
```

### Attaching Hooks

Pass them to `create()`:

```python
async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    on_request=on_request,
    on_response=on_response,
) as client:
    df = await client.get("customers")
    # >>> GET https://bc-server:7048/BC210/ODataV4/customers
    # <<< 200 https://bc-server:7048/BC210/ODataV4/customers (142ms)
```

### Metrics Example

```python
from collections import defaultdict

request_counts = defaultdict(int)
total_duration_ms = 0.0

def on_response(*, method, url, status_code, duration_ms):
    global total_duration_ms
    request_counts[status_code] += 1
    total_duration_ms += duration_ms

# After your work:
print(f"Total requests: {sum(request_counts.values())}")
print(f"Total time: {total_duration_ms:.0f}ms")
print(f"Status codes: {dict(request_counts)}")
```

### Hook Protocols

Both hooks are defined as `@runtime_checkable` protocols. Any callable with the right keyword-only signature works — functions, lambdas, bound methods, or callable objects.

```python
# RequestHook protocol
class RequestHook(Protocol):
    def __call__(self, *, method: str, url: str, params: dict[str, str] | None) -> None: ...

# ResponseHook protocol
class ResponseHook(Protocol):
    def __call__(self, *, method: str, url: str, status_code: int, duration_ms: float) -> None: ...
```

## Progress Callbacks

### Pagination Progress

Track page-by-page progress during `get()` or `get_stream()`:

```python
def on_progress(*, page: int, records_on_page: int, total_records: int, is_final: bool) -> None:
    status = "DONE" if is_final else "..."
    print(f"Page {page}: {records_on_page} records (total: {total_records}) {status}")

df = await client.get("customers", on_progress=on_progress)
# Page 1: 1000 records (total: 1000) ...
# Page 2: 1000 records (total: 2000) ...
# Page 3: 456 records (total: 2456) DONE
```

**ProgressCallback protocol:**

```python
class ProgressCallback(Protocol):
    def __call__(
        self,
        *,
        page: int,              # 1-indexed page number
        records_on_page: int,   # records on this page
        total_records: int,     # cumulative total
        is_final: bool,         # True on the last page
    ) -> None: ...
```

### Batch Progress

Track batch-by-batch progress during `get_batch()`:

```python
def on_batch_progress(*, batch: int, total_batches: int, successful: int, failed: int, is_final: bool) -> None:
    print(f"Batch {batch}/{total_batches}: {successful} ok, {failed} failed")

df = await client.get_batch(
    "customers",
    field="No",
    values=customer_ids,
    on_progress=on_batch_progress,
)
# Batch 1/10: 1 ok, 0 failed
# Batch 2/10: 2 ok, 0 failed
# ...
# Batch 10/10: 10 ok, 0 failed
```

**BatchProgressCallback protocol:**

```python
class BatchProgressCallback(Protocol):
    def __call__(
        self,
        *,
        batch: int,             # 1-indexed batch number
        total_batches: int,     # total number of batches
        successful: int,        # cumulative successful
        failed: int,            # cumulative failed
        is_final: bool,         # True on the last batch
    ) -> None: ...
```

## Streaming

`get_stream()` yields pages as individual DataFrames instead of loading everything into memory.

```python
async for page in client.get_stream("largeDataset"):
    # page is a pl.DataFrame with one page of results
    save_to_database(page)
```

Key differences from `get()`:
- No caching (pages are yielded, not stored)
- Memory-efficient for large datasets
- Each yielded DataFrame is one page of results
- Respects `max_pages` limit
- Supports `on_progress` callback

### With Query and Progress

```python
query = ODataQuery().filter(F.Active == True).select("No", "Name")

async for page in client.get_stream("customers", query=query, on_progress=on_progress):
    process(page)
```

## Batch Operations

`get_batch()` efficiently fetches records matching a large list of values by:

1. Chunking the values into batches (default: 50 per batch)
2. Building an `is_in()` filter for each batch
3. Running all batches concurrently (bounded by `max_connections` and `requests_per_minute`)
4. Concatenating results into a single DataFrame

### Basic Usage

```python
customer_ids = ["C001", "C002", ..., "C500"]

df = await client.get_batch(
    "customers",
    field="No",
    values=customer_ids,
    batch_size=50,
)
```

### With Additional Options

```python
df = await client.get_batch(
    "customers",
    field="No",
    values=customer_ids,
    batch_size=50,
    select=["No", "Name", "Balance_LCY"],
    expand=["SalesLines"],
    order_by=["Name asc"],
    additional_filter=(F.Blocked == False),
    use_cache=True,
)
```

### Error Handling

By default (`fail_fast=False`), failed batches are logged and skipped. The result contains data from successful batches only.

```python
# Continue on errors (default)
df = await client.get_batch("customers", "No", ids, fail_fast=False)

# Stop on first error
try:
    df = await client.get_batch("customers", "No", ids, fail_fast=True)
except RetryExhaustedError:
    print("A batch failed after retries")
```

### Batch Size Tuning

BC on-premises typically handles 50-100 values per `is_in()` filter well. Larger batches may hit URL length limits. Start with 50 and increase if your BC instance supports it.

## Delta Sync

Incremental data loading using `SystemModifiedAt` timestamps.

### get_since()

Fetch records modified after a timestamp:

```python
from datetime import datetime, timedelta, timezone

since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
updated = await client.get_since("customers", since)
```

Defaults to `use_cache=False` — delta syncs want fresh data.

You can combine with additional filters:

```python
query = ODataQuery().select("No", "Name", "SystemModifiedAt")
updated = await client.get_since("customers", since, query=query)
```

### get_before()

Fetch records not modified since a timestamp:

```python
before = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
stale = await client.get_before("customers", before)
```

Defaults to `use_cache=True` — historical data is unlikely to change.

### Delta Sync Pattern

```python
import json
from pathlib import Path
from datetime import datetime, timezone

CHECKPOINT_FILE = Path("last_sync.json")

# Load last sync timestamp
if CHECKPOINT_FILE.exists():
    checkpoint = json.loads(CHECKPOINT_FILE.read_text())
    last_sync = checkpoint["timestamp"]
else:
    last_sync = "1970-01-01T00:00:00Z"

# Fetch only new/updated records
updated = await client.get_since("customers", last_sync)

if not updated.is_empty():
    process_updates(updated)

# Save new checkpoint
CHECKPOINT_FILE.write_text(json.dumps({
    "timestamp": datetime.now(timezone.utc).isoformat()
}))
```

## Concurrency Tuning

### max_connections

Controls the httpx connection pool size and the asyncio semaphore. Default: 4.

```python
# More connections for faster parallel fetches
client = BCWebServiceClient.create(
    ...,
    max_connections=8,
)
```

BC on-premises typically handles 4-10 concurrent connections. Going above 10 may trigger rate limiting or connection refusals.

### requests_per_minute

Token-bucket rate limiter. Default: 550 req/min.

```python
# Slower for busy servers
client = BCWebServiceClient.create(..., requests_per_minute=300.0)

# Disable rate limiting entirely
client = BCWebServiceClient.create(..., requests_per_minute=None)
```

### max_burst

Controls how many requests can be sent immediately before rate limiting kicks in. Defaults to `max_connections` to prevent hammering the server on startup.

```python
# Allow larger burst for batch operations
client = BCWebServiceClient.create(
    ...,
    max_connections=4,
    requests_per_minute=550.0,
    max_burst=10,
)
```

### How They Interact

1. `max_connections` semaphore limits concurrent in-flight requests
2. Inside the semaphore, the rate limiter controls sustained throughput
3. `max_burst` lets N requests through immediately, then throttles to `requests_per_minute`

For `get_batch()`, all batches are submitted concurrently but naturally bounded by these controls.

## Retry Tuning

```python
client = BCWebServiceClient.create(
    ...,
    max_retries=5,       # default: 3
    retry_backoff=2.0,   # default: 1.0
)
```

Backoff formula: `retry_backoff * 2^attempt + random_jitter`

With defaults (backoff=1.0, retries=3):
- Attempt 1: immediate
- Attempt 2: ~1s delay
- Attempt 3: ~2s delay
- Attempt 4: ~4s delay

With backoff=2.0, retries=5:
- Attempt 1: immediate
- Attempt 2: ~2s
- Attempt 3: ~4s
- Attempt 4: ~8s
- Attempt 5: ~16s
- Attempt 6: ~32s

For `RateLimitError`, the `Retry-After` header value is used instead of the calculated backoff.

## Logging

Odyn logs under the `odyn` namespace (`odyn.client`, `odyn.sync`). Set `log_level` in `create()`:

```python
import logging

client = BCWebServiceClient.create(
    ...,
    log_level=logging.DEBUG,  # verbose HTTP request/response logging
)
```

Log format: `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`

Key log messages:
- `INFO`: Client init, cache hits/misses, page fetches, batch summaries
- `WARNING`: Retries, rate limits, failed batches
- `DEBUG`: Individual HTTP requests/responses, rate limit token acquisition
- `ERROR`: Retry exhaustion, server errors
