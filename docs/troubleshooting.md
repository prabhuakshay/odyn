# Troubleshooting

Common issues when working with Business Central on-premises OData Web Services and how to resolve them with Odyn.

## Connection Issues

### SSL Certificate Errors

**Symptom:** `SSLError: SSL/TLS error: certificate verify failed`

**Cause:** BC on-premises often uses self-signed certificates.

**Fix:** Disable SSL verification:

```python
client = BCWebServiceClient.create(
    ...,
    verify_ssl=False,
)
```

### Connection Refused

**Symptom:** `ConnectionError: Failed to connect to https://bc-server:7048`

**Possible causes:**

1. **Wrong port** — BC on-premises default ports are 7047 (SOAP), 7048 (OData), 7049 (Dev). Make sure you're using the OData port.
2. **Firewall** — The server may not allow connections on the OData port from your machine.
3. **Service not running** — The BC service tier may be stopped.
4. **Wrong server URL** — Verify the hostname/IP is correct and reachable.

### Timeout Errors

**Symptom:** `TimeoutError: Request timed out after 30.0s`

**Fix:** Increase the timeout:

```python
client = BCWebServiceClient.create(
    ...,
    timeout=120.0,  # 2 minutes
)
```

Large datasets or complex queries on busy BC servers may take longer. The default 30s is conservative.

## Authentication Issues

### HTTP 401 — AuthenticationError

**Symptom:** `[401] Unauthorized`

**Possible causes:**

1. **Wrong credentials** — Double-check username and password.
2. **Domain not specified** — For Windows auth, use `DOMAIN\user`:
   ```python
   auth = BasicAuth("MYDOMAIN\\svc_account", "password")
   ```
3. **Account locked** — The AD account may be locked after failed attempts.
4. **Auth type mismatch** — The BC instance may expect a different auth method than what you're sending.

### HTTP 403 — ForbiddenError

**Symptom:** `[403] Forbidden`

**Cause:** The user is authenticated but lacks permission to access the resource.

**Fix:** In Business Central, go to **Users** > select the user > **Permissions** and ensure they have access to the relevant pages/data.

## Query Issues

### HTTP 400 — ValidationError

**Symptom:** `[400] Bad Request`

**Common causes:**

1. **Invalid field name** — The field name doesn't exist on the entity. Check the entity's published fields in BC Web Services.
   ```python
   # Wrong: using a display name instead of the API field name
   query = ODataQuery().filter(F.Customer_Name == "John")
   # Right: use the actual field name from the web service
   query = ODataQuery().filter(F.Name == "John")
   ```

2. **Type mismatch** — Filtering a string field with a number or vice versa.
   ```python
   # Wrong: No is a string field
   query = ODataQuery().filter(F.No == 123)
   # Right:
   query = ODataQuery().filter(F.No == "123")
   ```

3. **Invalid expand** — The relation name doesn't exist or isn't published.

### HTTP 404 — NotFoundError

**Symptom:** `[404] Not Found`

**Possible causes:**

1. **Endpoint not published** — The web service must be published in BC under Administration > Web Services.
2. **Wrong endpoint name** — The name is case-sensitive and must match exactly what's published.
3. **Wrong instance name** — The BC instance in the URL doesn't exist.
4. **Record doesn't exist** — For `get_by_key()` or `get_by_id()`, the record wasn't found.

**Debugging:** Use `get_endpoints()` to see what's available:

```python
endpoints = await client.get_endpoints()
print(endpoints)
```

### Empty Results

**Symptom:** `get()` returns an empty DataFrame.

**Possible causes:**

1. **Filter too restrictive** — Relax or remove filters to test.
2. **Wrong company** — The `company` parameter must match the BC company name exactly (case-sensitive).
3. **No published data** — The web service page may exist but have no records.

**Debug by removing the query:**

```python
# Step 1: Try without filters
df = await client.get("customers")
print(f"Total records: {len(df)}")

# Step 2: Add filters back one at a time
df = await client.get("customers", query=ODataQuery().filter(F.Status == "Active"))
```

## Performance Issues

### Slow Queries

1. **Select only needed fields** — Reduces data transfer:
   ```python
   query = ODataQuery().select("No", "Name")  # instead of all fields
   ```

2. **Enable caching** — Avoid repeated API calls:
   ```python
   client = BCWebServiceClient.create(..., cache_dir="~/.cache/odyn", cache_ttl=3600)
   ```

3. **Use `get_stream()` for large datasets** — Process page-by-page instead of loading everything:
   ```python
   async for page in client.get_stream("largeDataset"):
       process(page)
   ```

4. **Tune batch size in `get_batch()`** — Default 50 values per batch is conservative. Try 100 if your BC instance handles it.

### Rate Limiting (HTTP 429)

**Symptom:** `[429] Too Many Requests` or slow throughput.

**Fix:** Reduce request rate:

```python
client = BCWebServiceClient.create(
    ...,
    requests_per_minute=200.0,  # slower than default 550
    max_connections=2,          # fewer concurrent connections
)
```

### Pagination Limit Reached

**Symptom:** Warning `Pagination limit reached: max_pages=100`

The default `max_pages=100` may not be enough for very large datasets.

**Fix:**

```python
client = BCWebServiceClient.create(
    ...,
    max_pages=500,  # allow more pages
)
```

Or use `get_stream()` to process page-by-page without memory concerns.

## Cache Issues

### Stale Data

**Symptom:** Getting outdated results even though BC data has changed.

**Fix:**

```python
# Force refresh for one query
df = await client.get("customers", use_cache=False)

# Clear entire cache
client.clear_cache()

# Or reduce TTL
client = BCWebServiceClient.create(..., cache_ttl=300)  # 5 minutes
```

### Disk Space

**Symptom:** Cache directory growing large.

**Fix:**

```python
# Remove expired entries
removed = client.cleanup_cache()

# Check cache size
stats = client.cache_stats
print(f"Disk usage: {stats['disk_bytes'] / 1024 / 1024:.1f} MB")

# Clear everything
client.clear_cache()
```

## Retry Issues

### RetryExhaustedError

**Symptom:** `Request failed after 4 attempts`

All retries were exhausted for a transient error (timeout, connection error, 429, or 5xx).

**Fixes:**

1. **Increase retries:** `max_retries=5`
2. **Increase backoff:** `retry_backoff=2.0` (longer waits between retries)
3. **Increase timeout:** `timeout=120.0`
4. **Check the last exception:** `e.last_exception` tells you what kept failing

```python
try:
    df = await client.get("customers")
except RetryExhaustedError as e:
    print(f"Failed after {e.attempts} attempts")
    print(f"Last error: {e.last_exception}")
    # Was it timeouts? Connection issues? Rate limits?
```

## OData-Specific Issues

### Field Names with Spaces

BC web services replace spaces with underscores in field names. Use underscores in your queries:

```python
# "Balance (LCY)" in BC becomes "Balance_LCY" in OData
query = ODataQuery().filter(F.Balance_LCY > 1000)
```

### Special Characters in Company Names

Company names with special characters work fine — Odyn URL-encodes them:

```python
client = BCWebServiceClient.create(
    ...,
    company="CRONUS International Ltd.",  # periods, spaces are fine
)
```

### SystemId vs Primary Key

- **Primary key** (`get_by_key`): The business key like `"C00010"` for a customer. Formatted as `endpoint('key')`.
- **SystemId** (`get_by_id`): A GUID like `"12345678-1234-1234-1234-123456789012"`. Formatted as `endpoint(guid)` (no quotes).

### OData Functions

The typed expression DSL doesn't cover OData functions like `contains()`, `startswith()`, `endswith()`, `substringof()`. Use `filter_raw()`:

```python
query = ODataQuery().filter_raw("contains(Name, 'Corp')")
query = ODataQuery().filter_raw("startswith(Email, 'sales')")
```

You can mix raw and typed filters:

```python
query = (
    ODataQuery()
    .filter_raw("contains(Name, 'Corp')")
    .filter(F.Balance > 0)
)
```
