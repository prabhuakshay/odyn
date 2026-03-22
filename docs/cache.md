# Caching

Odyn includes a file-based caching system that stores Polars DataFrames as Parquet files. Repeated queries hit the local cache instead of making HTTP requests, making subsequent fetches near-instant.

## Enabling the Cache

Pass `cache_dir` to `BCWebServiceClient.create()`:

```python
async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
    cache_dir="~/.cache/odyn",   # directory for cache files
    cache_ttl=3600,              # entries expire after 1 hour
) as client:
    df = await client.get("customers")   # cache miss — fetches from API
    df = await client.get("customers")   # cache hit — reads Parquet file
```

- `cache_dir` — path to the cache directory (created automatically). Supports `~` expansion.
- `cache_ttl` — default TTL in seconds for all entries. `None` means entries never expire.

## How It Works

Each cache entry is stored as two files:

```
~/.cache/odyn/
  a1b2c3d4e5...f6.parquet   # the DataFrame
  a1b2c3d4e5...f6.json      # metadata (URL, params, timestamps, TTL)
```

### Cache Keys

Keys are 64-character hex strings (SHA256 hashes) generated from the URL and sorted query parameters:

```python
key = ParquetCache.make_key(url, params)
# 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'
```

Parameter order does not affect the key — `{"a": "1", "b": "2"}` and `{"b": "2", "a": "1"}` produce the same key.

### Cache Reads

When `client.get()` is called with `use_cache=True` (default):

1. Generate cache key from URL + query params
2. Check if a valid (non-expired) entry exists
3. If hit: return the DataFrame from the Parquet file
4. If miss: fetch from API, store result, return

Empty DataFrames are never cached.

### TTL Expiration

An entry is expired if:
- Its stored `ttl_seconds` has elapsed, **OR**
- The cache's `default_ttl` has elapsed (even if the entry was written with a different TTL)

This means changing `default_ttl` takes effect immediately for all entries.

## Bypassing the Cache

```python
# Skip cache for a single request
df = await client.get("customers", use_cache=False)

# get_since() defaults to use_cache=False (delta syncs want fresh data)
updated = await client.get_since("customers", timestamp)
```

## Cache Management

### Via the Client

```python
# Remove all entries
removed = client.clear_cache()

# Remove only expired entries
removed = client.cleanup_cache()

# Check cache size
size = client.cache_size  # number of entries

# Get statistics
stats = client.cache_stats
# {"hits": 42, "misses": 7, "disk_bytes": 1048576}

if stats:
    total = stats["hits"] + stats["misses"]
    print(f"Hit rate: {stats['hits'] / max(1, total):.1%}")
```

### Via ParquetCache Directly

You can also use `ParquetCache` standalone (without the client):

```python
from pathlib import Path
from odyn import ParquetCache

cache = ParquetCache(Path("~/.cache/odyn").expanduser(), default_ttl=3600)

# Generate a key
key = ParquetCache.make_key("https://example.com/odata/customers", {"$top": "100"})

# Store a DataFrame
cache.set(key, df, url="https://example.com/odata/customers", params={"$top": "100"})

# Retrieve
cached_df = cache.get(key)
if cached_df is not None:
    print(f"Cache hit: {len(cached_df)} rows")

# Check existence (without loading the DataFrame)
if key in cache:
    print("Entry exists and is not expired")

if cache.exists(key):
    print("Same as above")

# Delete a specific entry
cache.delete(key)

# Clear everything
cache.clear()

# Remove expired entries
cache.cleanup()

# Size and stats
cache.size()   # number of entries
cache.stats()  # {"hits": N, "misses": N, "disk_bytes": N}
```

## CacheMetadata

Each entry's `.json` file stores a `CacheMetadata` dataclass:

```python
from odyn import CacheMetadata

# Fields
metadata.url          # str: original URL
metadata.params       # dict[str, str] | None: query parameters
metadata.created_at   # float: Unix timestamp
metadata.ttl_seconds  # int | None: TTL for this entry

# Properties
metadata.is_expired   # bool: whether TTL has elapsed
metadata.age          # float: seconds since creation
```

## ParquetCache API Summary

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__()` | `(cache_dir: Path, default_ttl: int \| None = None)` | Create cache. Directory is auto-created. |
| `get()` | `(key: str) -> pl.DataFrame \| None` | Get entry if valid, else `None`. |
| `set()` | `(key, df, *, url, params=None, ttl_seconds=None)` | Store DataFrame. TTL falls back to `default_ttl`. |
| `delete()` | `(key: str) -> bool` | Remove entry. Returns `True` if existed. |
| `exists()` | `(key: str) -> bool` | Check if valid (non-expired) entry exists. |
| `clear()` | `() -> int` | Remove all entries. Returns count. Resets stats. |
| `cleanup()` | `() -> int` | Remove expired entries. Returns count. |
| `size()` | `() -> int` | Total entries (may include expired). |
| `stats()` | `() -> dict[str, int]` | `{"hits", "misses", "disk_bytes"}` |
| `make_key()` | `(url, params=None) -> str` | Static. SHA256 hash, 64-char hex. |
| `__contains__()` | `(key: str) -> bool` | Supports `key in cache`. Same as `exists()`. |
