"""Tests for Parquet-based cache.

This module provides comprehensive tests for the odyn.cache module,
covering the ParquetCache class and CacheMetadata dataclass.

Test Categories:
    - CacheMetadata: dataclass properties, is_expired, age
    - ParquetCache creation: initialization, directory creation
    - make_key() method: key generation, determinism, parameter ordering
    - set() method: storing DataFrames, metadata, TTL handling
    - get() method: retrieval, expiration, missing keys
    - delete() method: removal, return values
    - exists() method: existence checking, expiration awareness
    - clear() method: clearing all entries
    - cleanup() method: removing expired entries
    - size() method: counting entries
    - __contains__ / __repr__: dunder methods
"""

import time
from pathlib import Path

import polars as pl
import pytest

from odyn.cache import CacheMetadata, ParquetCache

__all__ = []


# =============================================================================
# CacheMetadata Tests
# =============================================================================


class TestCacheMetadata:
    """Test suite for CacheMetadata dataclass.

    CacheMetadata stores metadata about cached entries including
    URL, params, creation time, and TTL.
    """

    def test_creates_metadata_with_all_fields(self) -> None:
        """Validate that CacheMetadata can be created with all fields."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params={"$filter": "active eq true"},
            created_at=1000.0,
            ttl_seconds=3600,
        )
        assert metadata.url == "https://api.example.com/data"
        assert metadata.params == {"$filter": "active eq true"}
        assert metadata.created_at == 1000.0
        assert metadata.ttl_seconds == 3600

    def test_creates_metadata_with_none_params(self) -> None:
        """Validate that CacheMetadata accepts None for params."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=1000.0,
            ttl_seconds=3600,
        )
        assert metadata.params is None

    def test_creates_metadata_with_none_ttl(self) -> None:
        """Validate that CacheMetadata accepts None for ttl_seconds."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=1000.0,
            ttl_seconds=None,
        )
        assert metadata.ttl_seconds is None


class TestCacheMetadataIsExpired:
    """Test suite for CacheMetadata.is_expired property."""

    def test_not_expired_when_ttl_is_none(self) -> None:
        """Validate that entries with no TTL never expire."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=0.0,  # Very old
            ttl_seconds=None,
        )
        assert metadata.is_expired is False

    def test_not_expired_when_within_ttl(self) -> None:
        """Validate that entries within TTL are not expired."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=time.time(),
            ttl_seconds=3600,
        )
        assert metadata.is_expired is False

    def test_expired_when_past_ttl(self) -> None:
        """Validate that entries past TTL are expired."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=time.time() - 10,  # 10 seconds ago
            ttl_seconds=5,  # 5 second TTL
        )
        assert metadata.is_expired is True

    def test_expired_exactly_at_ttl_boundary(self) -> None:
        """Validate behavior at exact TTL boundary."""
        now = time.time()
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=now - 5.001,  # Just past 5 seconds
            ttl_seconds=5,
        )
        assert metadata.is_expired is True


class TestCacheMetadataAge:
    """Test suite for CacheMetadata.age property."""

    def test_age_is_positive(self) -> None:
        """Validate that age is a positive number."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=time.time() - 10,
            ttl_seconds=3600,
        )
        assert metadata.age >= 10
        assert metadata.age < 11  # Should be close to 10

    def test_age_of_new_entry_is_small(self) -> None:
        """Validate that age of newly created entry is near zero."""
        metadata = CacheMetadata(
            url="https://api.example.com/data",
            params=None,
            created_at=time.time(),
            ttl_seconds=3600,
        )
        assert metadata.age < 1


# =============================================================================
# ParquetCache Creation Tests
# =============================================================================


class TestParquetCacheCreation:
    """Test suite for ParquetCache initialization."""

    def test_creates_cache_directory(self, tmp_path: Path) -> None:
        """Validate that ParquetCache creates the cache directory."""
        cache_dir = tmp_path / "cache"
        assert not cache_dir.exists()

        ParquetCache(cache_dir)
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_creates_nested_cache_directory(self, tmp_path: Path) -> None:
        """Validate that ParquetCache creates nested directories."""
        cache_dir = tmp_path / "deeply" / "nested" / "cache"
        assert not cache_dir.exists()

        ParquetCache(cache_dir)
        assert cache_dir.exists()

    def test_accepts_existing_directory(self, tmp_path: Path) -> None:
        """Validate that ParquetCache accepts an existing directory."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        cache = ParquetCache(cache_dir)
        assert cache.size() == 0

    def test_stores_default_ttl(self, tmp_path: Path) -> None:
        """Validate that ParquetCache stores the default TTL."""
        cache = ParquetCache(tmp_path / "cache", default_ttl=3600)
        assert cache._default_ttl == 3600

    def test_default_ttl_is_none_by_default(self, tmp_path: Path) -> None:
        """Validate that default_ttl is None when not specified."""
        cache = ParquetCache(tmp_path / "cache")
        assert cache._default_ttl is None


# =============================================================================
# make_key() Method Tests
# =============================================================================


class TestMakeKey:
    """Test suite for ParquetCache.make_key() static method.

    make_key() generates deterministic cache keys from URL and parameters.
    """

    def test_generates_64_char_hex_string(self) -> None:
        """Validate that make_key produces a 64-character hex string."""
        key = ParquetCache.make_key("https://api.example.com/data")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_url_produces_same_key(self) -> None:
        """Validate that the same URL always produces the same key."""
        url = "https://api.example.com/data"
        key1 = ParquetCache.make_key(url)
        key2 = ParquetCache.make_key(url)
        assert key1 == key2

    def test_different_urls_produce_different_keys(self) -> None:
        """Validate that different URLs produce different keys."""
        key1 = ParquetCache.make_key("https://api.example.com/data1")
        key2 = ParquetCache.make_key("https://api.example.com/data2")
        assert key1 != key2

    def test_params_affect_key(self) -> None:
        """Validate that parameters affect the generated key."""
        url = "https://api.example.com/data"
        key1 = ParquetCache.make_key(url)
        key2 = ParquetCache.make_key(url, {"page": "1"})
        assert key1 != key2

    def test_param_order_does_not_affect_key(self) -> None:
        """Validate that parameter order doesn't affect the key."""
        url = "https://api.example.com/data"
        key1 = ParquetCache.make_key(url, {"a": "1", "b": "2"})
        key2 = ParquetCache.make_key(url, {"b": "2", "a": "1"})
        assert key1 == key2

    def test_empty_params_same_as_none(self) -> None:
        """Validate that empty params dict produces same key as None."""
        url = "https://api.example.com/data"
        key1 = ParquetCache.make_key(url, None)
        key2 = ParquetCache.make_key(url, {})
        # Empty dict is falsy, so should be same as None
        assert key1 == key2

    def test_special_chars_in_params_are_handled(self) -> None:
        """Validate that special characters in params don't cause issues."""
        url = "https://api.example.com/data"
        key = ParquetCache.make_key(url, {"$filter": "name eq 'John'"})
        assert len(key) == 64

    @pytest.mark.parametrize(
        "params",
        [
            {"$filter": "status eq 'active'"},
            {"$select": "Name,Age,Balance"},
            {"$top": "100", "$skip": "50"},
            {"key": "value with spaces"},
            {"key": "value&with&ampersands"},
        ],
        ids=["filter", "select", "top_skip", "spaces", "ampersands"],
    )
    def test_various_param_formats(self, params: dict[str, str]) -> None:
        """Validate that various parameter formats produce valid keys.

        Args:
            params: Query parameters to include in key generation.
        """
        key = ParquetCache.make_key("https://api.example.com", params)
        assert len(key) == 64


# =============================================================================
# set() Method Tests
# =============================================================================


class TestSetMethod:
    """Test suite for ParquetCache.set() method.

    set() stores a DataFrame and its metadata in the cache.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

    def test_stores_dataframe_as_parquet(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that set() stores the DataFrame as a Parquet file."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        parquet_path = cache._cache_dir / f"{key}.parquet"
        assert parquet_path.exists()

    def test_stores_metadata_as_json(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that set() stores metadata as a JSON file."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        metadata_path = cache._cache_dir / f"{key}.json"
        assert metadata_path.exists()

    def test_metadata_contains_url(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that stored metadata contains the URL."""
        key = "test_key"
        url = "https://api.example.com/data"
        cache.set(key, sample_df, url=url)

        metadata = cache._load_metadata(key)
        assert metadata is not None
        assert metadata.url == url

    def test_metadata_contains_params(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that stored metadata contains the params."""
        key = "test_key"
        params = {"$filter": "active eq true"}
        cache.set(key, sample_df, url="https://api.example.com", params=params)

        metadata = cache._load_metadata(key)
        assert metadata is not None
        assert metadata.params == params

    def test_uses_explicit_ttl(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that set() uses the explicit TTL when provided."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=7200)

        metadata = cache._load_metadata(key)
        assert metadata is not None
        assert metadata.ttl_seconds == 7200

    def test_uses_default_ttl_when_not_specified(self, tmp_path: Path, sample_df: pl.DataFrame) -> None:
        """Validate that set() uses default TTL when ttl_seconds not provided."""
        cache = ParquetCache(tmp_path / "cache", default_ttl=3600)
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        metadata = cache._load_metadata(key)
        assert metadata is not None
        assert metadata.ttl_seconds == 3600

    def test_explicit_ttl_overrides_default(self, tmp_path: Path, sample_df: pl.DataFrame) -> None:
        """Validate that explicit TTL overrides the default."""
        cache = ParquetCache(tmp_path / "cache", default_ttl=3600)
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=7200)

        metadata = cache._load_metadata(key)
        assert metadata is not None
        assert metadata.ttl_seconds == 7200

    def test_overwrites_existing_entry(self, cache: ParquetCache) -> None:
        """Validate that set() overwrites an existing entry."""
        key = "test_key"
        df1 = pl.DataFrame({"value": [1]})
        df2 = pl.DataFrame({"value": [2]})

        cache.set(key, df1, url="https://api.example.com")
        cache.set(key, df2, url="https://api.example.com")

        result = cache.get(key)
        assert result is not None
        assert result["value"][0] == 2


# =============================================================================
# get() Method Tests
# =============================================================================


class TestGetMethod:
    """Test suite for ParquetCache.get() method.

    get() retrieves a cached DataFrame if it exists and hasn't expired.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

    def test_retrieves_cached_dataframe(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that get() retrieves a cached DataFrame."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        result = cache.get(key)
        assert result is not None
        assert result.equals(sample_df)

    def test_returns_none_for_missing_key(self, cache: ParquetCache) -> None:
        """Validate that get() returns None for a missing key."""
        result = cache.get("nonexistent_key")
        assert result is None

    def test_returns_none_for_expired_entry(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that get() returns None for an expired entry."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=0)

        # Wait a tiny bit to ensure expiration
        time.sleep(0.01)

        result = cache.get(key)
        assert result is None

    def test_returns_dataframe_when_not_expired(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that get() returns DataFrame when entry hasn't expired."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=3600)

        result = cache.get(key)
        assert result is not None
        assert result.equals(sample_df)

    def test_returns_none_when_parquet_missing_but_metadata_exists(self, cache: ParquetCache) -> None:
        """Validate behavior when Parquet file is missing but metadata exists."""
        key = "test_key"
        # Manually create only the metadata file
        metadata = CacheMetadata(
            url="https://api.example.com",
            params=None,
            created_at=time.time(),
            ttl_seconds=3600,
        )
        cache._save_metadata(key, metadata)

        result = cache.get(key)
        assert result is None


# =============================================================================
# delete() Method Tests
# =============================================================================


class TestDeleteMethod:
    """Test suite for ParquetCache.delete() method.

    delete() removes a cache entry and returns whether it existed.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3]})

    def test_deletes_existing_entry(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that delete() removes an existing entry."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        cache.delete(key)

        assert cache.get(key) is None

    def test_returns_true_for_existing_entry(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that delete() returns True when entry existed."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        result = cache.delete(key)
        assert result is True

    def test_returns_false_for_missing_entry(self, cache: ParquetCache) -> None:
        """Validate that delete() returns False when entry didn't exist."""
        result = cache.delete("nonexistent_key")
        assert result is False

    def test_removes_both_parquet_and_metadata(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that delete() removes both the Parquet file and metadata."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        parquet_path = cache._parquet_path(key)
        metadata_path = cache._metadata_path(key)

        assert parquet_path.exists()
        assert metadata_path.exists()

        cache.delete(key)

        assert not parquet_path.exists()
        assert not metadata_path.exists()


# =============================================================================
# exists() Method Tests
# =============================================================================


class TestExistsMethod:
    """Test suite for ParquetCache.exists() method.

    exists() checks if a non-expired entry exists.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3]})

    def test_returns_true_for_existing_entry(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that exists() returns True for an existing entry."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        assert cache.exists(key) is True

    def test_returns_false_for_missing_entry(self, cache: ParquetCache) -> None:
        """Validate that exists() returns False for a missing entry."""
        assert cache.exists("nonexistent_key") is False

    def test_returns_false_for_expired_entry(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that exists() returns False for an expired entry."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=0)

        time.sleep(0.01)

        assert cache.exists(key) is False

    def test_returns_true_for_non_expired_entry(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that exists() returns True for a non-expired entry."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=3600)

        assert cache.exists(key) is True


# =============================================================================
# clear() Method Tests
# =============================================================================


class TestClearMethod:
    """Test suite for ParquetCache.clear() method.

    clear() removes all cache entries.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3]})

    def test_removes_all_entries(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that clear() removes all entries."""
        cache.set("key1", sample_df, url="https://api.example.com/1")
        cache.set("key2", sample_df, url="https://api.example.com/2")
        cache.set("key3", sample_df, url="https://api.example.com/3")

        cache.clear()

        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_returns_count_of_removed_entries(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that clear() returns the count of removed entries."""
        cache.set("key1", sample_df, url="https://api.example.com/1")
        cache.set("key2", sample_df, url="https://api.example.com/2")

        count = cache.clear()
        assert count == 2

    def test_returns_zero_for_empty_cache(self, cache: ParquetCache) -> None:
        """Validate that clear() returns 0 for an empty cache."""
        count = cache.clear()
        assert count == 0

    def test_handles_orphaned_parquet_file(self, cache: ParquetCache) -> None:
        """Validate that clear() handles orphaned parquet files (no metadata).

        This covers the edge case where a .parquet file exists but has no
        corresponding .json metadata file. delete() will still return True
        because the parquet file exists.
        """
        # Create an orphaned parquet file (no metadata)
        orphan_key = "orphaned"
        parquet_path = cache._cache_dir / f"{orphan_key}.parquet"
        parquet_path.write_bytes(b"dummy")

        # clear() should still count it
        count = cache.clear()
        assert count == 1
        assert not parquet_path.exists()


# =============================================================================
# cleanup() Method Tests
# =============================================================================


class TestCleanupMethod:
    """Test suite for ParquetCache.cleanup() method.

    cleanup() removes only expired entries.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3]})

    def test_removes_expired_entries(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that cleanup() removes expired entries."""
        cache.set("expired", sample_df, url="https://api.example.com/expired", ttl_seconds=0)
        cache.set("valid", sample_df, url="https://api.example.com/valid", ttl_seconds=3600)

        time.sleep(0.01)

        cache.cleanup()

        assert cache.get("expired") is None
        assert cache.get("valid") is not None

    def test_returns_count_of_removed_entries(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that cleanup() returns the count of removed entries."""
        cache.set("expired1", sample_df, url="https://api.example.com/1", ttl_seconds=0)
        cache.set("expired2", sample_df, url="https://api.example.com/2", ttl_seconds=0)
        cache.set("valid", sample_df, url="https://api.example.com/3", ttl_seconds=3600)

        time.sleep(0.01)

        count = cache.cleanup()
        assert count == 2

    def test_keeps_non_expired_entries(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that cleanup() keeps non-expired entries."""
        cache.set("key1", sample_df, url="https://api.example.com/1", ttl_seconds=3600)
        cache.set("key2", sample_df, url="https://api.example.com/2", ttl_seconds=3600)

        count = cache.cleanup()

        assert count == 0
        assert cache.size() == 2

    def test_returns_zero_when_nothing_expired(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that cleanup() returns 0 when no entries are expired."""
        cache.set("key", sample_df, url="https://api.example.com", ttl_seconds=3600)

        count = cache.cleanup()
        assert count == 0


# =============================================================================
# size() Method Tests
# =============================================================================


class TestSizeMethod:
    """Test suite for ParquetCache.size() method.

    size() returns the number of cached entries.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3]})

    def test_returns_zero_for_empty_cache(self, cache: ParquetCache) -> None:
        """Validate that size() returns 0 for an empty cache."""
        assert cache.size() == 0

    def test_returns_correct_count(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that size() returns the correct entry count."""
        cache.set("key1", sample_df, url="https://api.example.com/1")
        cache.set("key2", sample_df, url="https://api.example.com/2")
        cache.set("key3", sample_df, url="https://api.example.com/3")

        assert cache.size() == 3

    def test_decreases_after_delete(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that size() decreases after deletion."""
        cache.set("key1", sample_df, url="https://api.example.com/1")
        cache.set("key2", sample_df, url="https://api.example.com/2")

        cache.delete("key1")

        assert cache.size() == 1


# =============================================================================
# __contains__ (in operator) Tests
# =============================================================================


class TestContainsOperator:
    """Test suite for ParquetCache.__contains__ method (in operator).

    The `in` operator checks if a non-expired entry exists.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3]})

    def test_returns_true_for_existing_key(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that `in` returns True for an existing key."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        assert key in cache

    def test_returns_false_for_missing_key(self, cache: ParquetCache) -> None:
        """Validate that `in` returns False for a missing key."""
        assert "nonexistent_key" not in cache

    def test_returns_false_for_expired_key(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that `in` returns False for an expired key."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=0)

        time.sleep(0.01)

        assert key not in cache


# =============================================================================
# __repr__ Tests
# =============================================================================


class TestRepr:
    """Test suite for ParquetCache.__repr__ method."""

    def test_repr_format(self, tmp_path: Path) -> None:
        """Validate the format of __repr__ output."""
        cache_dir = tmp_path / "cache"
        cache = ParquetCache(cache_dir)

        repr_str = repr(cache)

        assert "ParquetCache" in repr_str
        assert "entries=0" in repr_str

    def test_repr_shows_entry_count(self, tmp_path: Path) -> None:
        """Validate that __repr__ shows the correct entry count."""
        cache = ParquetCache(tmp_path / "cache")
        df = pl.DataFrame({"id": [1]})
        cache.set("key1", df, url="https://api.example.com/1")
        cache.set("key2", df, url="https://api.example.com/2")

        repr_str = repr(cache)

        assert "entries=2" in repr_str


# =============================================================================
# Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Integration tests for full cache workflows."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache", default_ttl=3600)

    def test_full_workflow(self, cache: ParquetCache) -> None:
        """Validate a complete cache workflow: set, get, exists, delete."""
        url = "https://api.example.com/data"
        params = {"$filter": "active eq true"}
        df = pl.DataFrame({"id": [1, 2, 3], "name": ["A", "B", "C"]})

        # Generate key
        key = ParquetCache.make_key(url, params)

        # Verify not in cache
        assert key not in cache
        assert cache.get(key) is None

        # Store
        cache.set(key, df, url=url, params=params)

        # Verify in cache
        assert key in cache
        assert cache.size() == 1

        # Retrieve and verify
        cached = cache.get(key)
        assert cached is not None
        assert cached.equals(df)

        # Delete
        assert cache.delete(key) is True
        assert key not in cache
        assert cache.size() == 0

    def test_multiple_entries_workflow(self, cache: ParquetCache) -> None:
        """Validate workflow with multiple cache entries."""
        df = pl.DataFrame({"value": [1]})

        # Add multiple entries
        for i in range(5):
            key = f"key_{i}"
            cache.set(key, df, url=f"https://api.example.com/{i}")

        assert cache.size() == 5

        # Clear all
        removed = cache.clear()
        assert removed == 5
        assert cache.size() == 0

    def test_expiration_workflow(self, tmp_path: Path) -> None:
        """Validate TTL expiration workflow."""
        cache = ParquetCache(tmp_path / "cache")
        df = pl.DataFrame({"value": [1]})

        # Add entries with different TTLs
        cache.set("short_ttl", df, url="https://api.example.com/short", ttl_seconds=0)
        cache.set("long_ttl", df, url="https://api.example.com/long", ttl_seconds=3600)

        time.sleep(0.01)

        # Short TTL should be expired
        assert "short_ttl" not in cache
        assert cache.get("short_ttl") is None

        # Long TTL should still be valid
        assert "long_ttl" in cache
        assert cache.get("long_ttl") is not None

        # Cleanup should remove only expired
        removed = cache.cleanup()
        assert removed == 1
        assert cache.size() == 1


# =============================================================================
# stats() Method Tests
# =============================================================================


class TestStatsMethod:
    """Test suite for ParquetCache.stats() method.

    stats() returns cache statistics including hits, misses, and disk usage.
    """

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ParquetCache:
        """Create a cache instance for testing."""
        return ParquetCache(tmp_path / "cache")

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

    def test_stats_initial_values(self, cache: ParquetCache) -> None:
        """Validate that stats start at zero."""
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["disk_bytes"] == 0

    def test_stats_tracks_hits(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that cache hits increment the hit counter."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        cache.get(key)
        cache.get(key)
        cache.get(key)

        stats = cache.stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 0

    def test_stats_tracks_misses_for_missing_key(self, cache: ParquetCache) -> None:
        """Validate that cache misses for missing keys are tracked."""
        cache.get("nonexistent_key")
        cache.get("another_missing")

        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 2

    def test_stats_tracks_misses_for_expired_key(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that cache misses for expired keys are tracked."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com", ttl_seconds=0)

        time.sleep(0.01)
        cache.get(key)

        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 1

    def test_stats_disk_bytes(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that disk_bytes reflects actual file sizes."""
        cache.set("key1", sample_df, url="https://api.example.com/1")

        stats = cache.stats()
        assert stats["disk_bytes"] > 0

        # Add another entry
        cache.set("key2", sample_df, url="https://api.example.com/2")

        stats2 = cache.stats()
        assert stats2["disk_bytes"] > stats["disk_bytes"]

    def test_stats_disk_bytes_decreases_after_delete(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that disk_bytes decreases after deleting entries."""
        cache.set("key1", sample_df, url="https://api.example.com/1")
        cache.set("key2", sample_df, url="https://api.example.com/2")

        stats_before = cache.stats()
        cache.delete("key1")
        stats_after = cache.stats()

        assert stats_after["disk_bytes"] < stats_before["disk_bytes"]

    def test_clear_resets_hit_miss_counters(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate that clear() resets hit/miss counters."""
        key = "test_key"
        cache.set(key, sample_df, url="https://api.example.com")

        cache.get(key)  # Hit
        cache.get("missing")  # Miss

        stats_before = cache.stats()
        assert stats_before["hits"] == 1
        assert stats_before["misses"] == 1

        cache.clear()

        stats_after = cache.stats()
        assert stats_after["hits"] == 0
        assert stats_after["misses"] == 0
        assert stats_after["disk_bytes"] == 0

    def test_stats_combined_hits_and_misses(self, cache: ParquetCache, sample_df: pl.DataFrame) -> None:
        """Validate tracking of mixed hits and misses."""
        cache.set("key1", sample_df, url="https://api.example.com/1")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("missing1")  # Miss
        cache.get("key1")  # Hit
        cache.get("missing2")  # Miss

        stats = cache.stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 2
