"""Parquet-based cache for OData query results.

This module provides file-based caching for Polars DataFrames using the
Parquet format. Each cache entry consists of:

- A `.parquet` file containing the serialized DataFrame
- A `.json` file containing metadata (URL, params, timestamps, TTL)

Key Features:
    - Parquet storage for fast, compressed, columnar data
    - TTL-based expiration with per-entry or default TTL
    - SHA256 cache keys for deterministic, URL-safe identifiers
    - JSON metadata for debugging and introspection

Example:
    >>> from pathlib import Path
    >>> from odyn.cache import ParquetCache
    >>>
    >>> cache = ParquetCache(Path("~/.cache/odyn").expanduser(), default_ttl=3600)
    >>> key = ParquetCache.make_key(url, params)
    >>> cache.set(key, df, url=url, params=params)
    >>>
    >>> if (cached := cache.get(key)) is not None:
    ...     print("Cache hit!")
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CacheMetadata",
    "ParquetCache",
]


@dataclass(slots=True)
class CacheMetadata:
    """Metadata stored alongside each cached Parquet file.

    Attributes:
        url: The original URL used to fetch the data.
        params: The query parameters used in the request.
        created_at: Unix timestamp when the entry was created.
        ttl_seconds: Time-to-live in seconds. None means no expiration.

    Example:
        >>> metadata = CacheMetadata(
        ...     url="https://api.example.com/odata/customers",
        ...     params={"$filter": "active eq true"},
        ...     created_at=time.time(),
        ...     ttl_seconds=3600,
        ... )
        >>> metadata.is_expired
        False
        >>> metadata.age
        0.001
    """

    url: str
    params: dict[str, str] | None
    created_at: float
    ttl_seconds: int | None

    @property
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL.

        Returns:
            True if the entry is expired, False otherwise.
            Always returns False if ttl_seconds is None.
        """
        if self.ttl_seconds is None:
            return False
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age(self) -> float:
        """Calculate the age of this cache entry.

        Returns:
            Seconds elapsed since this entry was created.
        """
        return time.time() - self.created_at


class ParquetCache:
    """File-based cache storing DataFrames as Parquet with JSON metadata.

    Each cache entry consists of two files:
        - `{key}.parquet` - The cached DataFrame
        - `{key}.json` - Metadata (URL, params, timestamps, TTL)

    Attributes:
        cache_dir: Directory where cache files are stored.
        default_ttl: Default TTL in seconds for new entries.

    Example:
        >>> from pathlib import Path
        >>> cache = ParquetCache(Path("/tmp/odyn_cache"), default_ttl=3600)
        >>> url = "https://api.example.com/odata/customers"
        >>> params = {"$filter": "name eq 'John'"}
        >>> key = ParquetCache.make_key(url, params)
        >>>
        >>> # Store a DataFrame
        >>> cache.set(key, df, url=url, params=params)
        >>>
        >>> # Retrieve it later
        >>> if (cached := cache.get(key)) is not None:
        ...     print(f"Cache hit! {cached.shape}")
        >>>
        >>> # Check existence without loading
        >>> if key in cache:
        ...     print("Entry exists")
    """

    __slots__ = ("_cache_dir", "_default_ttl")

    def __init__(self, cache_dir: Path, default_ttl: int | None = None) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files. Created if it doesn't exist.
            default_ttl: Default TTL in seconds for entries without explicit TTL.
                         None means entries never expire by default.
        """
        self._cache_dir = cache_dir
        self._default_ttl = default_ttl
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _parquet_path(self, key: str) -> Path:
        """Get the path to the Parquet file for a cache key."""
        return self._cache_dir / f"{key}.parquet"

    def _metadata_path(self, key: str) -> Path:
        """Get the path to the metadata JSON file for a cache key."""
        return self._cache_dir / f"{key}.json"

    def _load_metadata(self, key: str) -> CacheMetadata | None:
        """Load metadata for a cache key.

        Args:
            key: The cache key.

        Returns:
            CacheMetadata if the metadata file exists, None otherwise.
        """
        path = self._metadata_path(key)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return CacheMetadata(**data)

    def _save_metadata(self, key: str, metadata: CacheMetadata) -> None:
        """Save metadata for a cache key.

        Args:
            key: The cache key.
            metadata: The metadata to save.
        """
        self._metadata_path(key).write_text(json.dumps(asdict(metadata)))

    def get(self, key: str) -> pl.DataFrame | None:
        """Retrieve a cached DataFrame.

        Args:
            key: The cache key, typically generated by `make_key()`.

        Returns:
            The cached DataFrame if found and not expired, None otherwise.

        Example:
            >>> df = cache.get(key)
            >>> if df is not None:
            ...     print(f"Loaded {len(df)} rows from cache")
        """
        metadata = self._load_metadata(key)
        if metadata is None or metadata.is_expired:
            return None

        parquet_path = self._parquet_path(key)
        if not parquet_path.exists():
            return None

        return pl.read_parquet(parquet_path)

    def set(
        self,
        key: str,
        df: pl.DataFrame,
        *,
        url: str,
        params: dict[str, str] | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store a DataFrame in the cache.

        Args:
            key: The cache key, typically generated by `make_key()`.
            df: The Polars DataFrame to cache.
            url: The original URL (stored as metadata for debugging).
            params: The query parameters (stored as metadata).
            ttl_seconds: Time-to-live in seconds. If None, uses the cache's
                         default_ttl. If both are None, the entry never expires.

        Example:
            >>> key = ParquetCache.make_key(url, params)
            >>> cache.set(key, df, url=url, params=params, ttl_seconds=3600)
        """
        df.write_parquet(self._parquet_path(key))

        metadata = CacheMetadata(
            url=url,
            params=params,
            created_at=time.time(),
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
        )
        self._save_metadata(key, metadata)

    def delete(self, key: str) -> bool:
        """Remove a cache entry.

        Args:
            key: The cache key to delete.

        Returns:
            True if an entry was deleted, False if the key didn't exist.

        Example:
            >>> if cache.delete(key):
            ...     print("Entry removed")
            ... else:
            ...     print("Key not found")
        """
        parquet_path = self._parquet_path(key)
        metadata_path = self._metadata_path(key)

        existed = parquet_path.exists() or metadata_path.exists()
        parquet_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        return existed

    def exists(self, key: str) -> bool:
        """Check if a non-expired entry exists.

        This method checks both that the entry exists and that it hasn't
        expired, without loading the full DataFrame.

        Args:
            key: The cache key to check.

        Returns:
            True if a valid (non-expired) entry exists, False otherwise.

        Example:
            >>> if cache.exists(key):
            ...     df = cache.get(key)  # Guaranteed to succeed
        """
        metadata = self._load_metadata(key)
        if metadata is None or metadata.is_expired:
            return False
        return self._parquet_path(key).exists()

    def clear(self) -> int:
        """Remove all cache entries.

        Returns:
            The number of entries that were removed.

        Example:
            >>> count = cache.clear()
            >>> print(f"Removed {count} entries")
        """
        count = 0
        for parquet_file in self._cache_dir.glob("*.parquet"):
            key = parquet_file.stem
            self.delete(key)
            count += 1
        return count

    def cleanup(self) -> int:
        """Remove expired cache entries.

        This method should be called periodically to free up disk space.
        It only removes entries that have exceeded their TTL.

        Returns:
            The number of expired entries that were removed.

        Example:
            >>> removed = cache.cleanup()
            >>> print(f"Cleaned up {removed} expired entries")
        """
        count = 0
        for metadata_file in self._cache_dir.glob("*.json"):
            key = metadata_file.stem
            metadata = self._load_metadata(key)
            if metadata and metadata.is_expired:
                self.delete(key)
                count += 1
        return count

    def size(self) -> int:
        """Return the number of cached entries.

        Returns:
            Total number of cache entries (may include expired entries).

        Example:
            >>> print(f"Cache contains {cache.size()} entries")
        """
        return len(list(self._cache_dir.glob("*.parquet")))

    @staticmethod
    def make_key(url: str, params: dict[str, str] | None = None) -> str:
        """Generate a deterministic cache key from URL and parameters.

        Creates a SHA256 hash of the URL and sorted, URL-encoded parameters.
        This ensures:
            - Consistent key length (64 hex characters)
            - URL-safe characters only
            - Parameter order doesn't affect the key
            - Special characters in values are handled correctly

        Args:
            url: The base URL.
            params: Optional query parameters. Order doesn't matter.

        Returns:
            A 64-character hexadecimal string (SHA256 hash).

        Example:
            >>> ParquetCache.make_key("https://api.example.com/data", {"page": "1"})
            'a1b2c3d4...'  # 64 char hex string

            >>> # Parameter order doesn't matter
            >>> key1 = ParquetCache.make_key(url, {"b": "2", "a": "1"})
            >>> key2 = ParquetCache.make_key(url, {"a": "1", "b": "2"})
            >>> key1 == key2
            True
        """
        key_data = url
        if params:
            key_data += "?" + urlencode(sorted(params.items()))
        return hashlib.sha256(key_data.encode()).hexdigest()

    def __contains__(self, key: str) -> bool:
        """Support `in` operator for checking key existence.

        Args:
            key: The cache key to check.

        Returns:
            True if a valid (non-expired) entry exists.

        Example:
            >>> if key in cache:
            ...     print("Cache hit!")
        """
        return self.exists(key)

    def __repr__(self) -> str:
        """Return a string representation of the cache.

        Returns:
            A string showing the cache directory and entry count.
        """
        return f"<ParquetCache dir={self._cache_dir!r} entries={self.size()}>"
