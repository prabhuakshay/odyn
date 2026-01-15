# Caching Guide

Odyn includes a high-performance caching system designed for data Engineering workflows. It stores Polars DataFrames as Parquet files on disk, ensuring that repeated queries are near-instant and don't consume Business Central API quota.

## How it Works

When caching is enabled:
1. Odyn generates a unique SHA256 key based on the request URL and query parameters.
2. It checks if a corresponding `.parquet` file exists in the `cache_dir`.
3. If the file exists and has not expired (based on TTL), the DataFrame is read directly from disk.
4. If not found or expired, the data is fetched from the API and then saved to the cache for future use.

## Configuration

You enable caching by passing `cache_dir` and `cache_ttl` to the client factory.

```python
from pathlib import Path

client = BCWebServiceClient.create(
    ...,
    cache_dir=Path("./.odyn_cache"),
    cache_ttl=3600  # 1 hour
)
```

## Management

### Cache Statistics

Monitor cache performance with the `cache_stats` property:

```python
stats = client.cache_stats
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
print(f"Disk usage: {stats['disk_bytes'] / 1024:.1f} KB")
```

The stats include:
- `hits`: Number of cache hits (data served from disk)
- `misses`: Number of cache misses (data fetched from API)
- `disk_bytes`: Total size of cached files on disk

### Cleaning Expired Entries

You can manually trigger a cleanup of expired entries to save disk space.

```python
removed = client.cleanup_cache()
print(f"Removed {removed} expired entries")
```

### Clearing the Cache

To remove all cached data regardless of expiration:

```python
removed = client.clear_cache()
print(f"Cleared {removed} entries")
```

### Cache Size

Check the number of entries in the cache:

```python
print(f"Cache contains {client.cache_size} entries")
```

## Advanced Usage

The `ParquetCache` class can be used independently of the `BCWebServiceClient` if you need to cache DataFrames from other sources.

```python
from odyn.cache import ParquetCache

cache = ParquetCache(Path("cache_path"))
cache.set("my_key", df, url="https://example.com")
```

### Metadata

Each cache entry is accompanied by a `.json` metadata file containing the original URL, parameters, creation timestamp, and TTL. This information is used by Odyn to validate the cache entry.
