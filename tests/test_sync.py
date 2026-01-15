"""Tests for the odyn.sync module (synchronous client wrapper)."""

from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from odyn.auth import BasicAuth
from odyn.sync import BCWebServiceClientSync


class TestBCWebServiceClientSyncCreate:
    """Tests for BCWebServiceClientSync.create() factory method."""

    def test_create_returns_sync_client(self):
        """create() returns a BCWebServiceClientSync instance."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert isinstance(client, BCWebServiceClientSync)
        client.close()

    def test_create_wraps_async_client(self):
        """create() wraps an async BCWebServiceClient."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client._client is not None
        assert client._client.base_url == "https://bc-server:7048/BC210/ODataV4"
        client.close()

    def test_create_passes_all_parameters(self):
        """create() passes all parameters to async client."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            company="CRONUS",
            timeout=60.0,
            max_pages=50,
            verify_ssl=False,
            max_retries=5,
            retry_backoff=2.0,
            max_connections=8,
            requests_per_minute=300.0,
            max_burst=10,
        )
        assert client._client.company == "CRONUS"
        assert client._client.timeout == 60.0
        assert client._client.max_pages == 50
        assert client._client.verify_ssl is False
        assert client._client.max_retries == 5
        assert client._client.retry_backoff == 2.0
        assert client._client.max_connections == 8
        assert client._client.requests_per_minute == 300.0
        assert client._client.max_burst == 10
        client.close()


class TestBCWebServiceClientSyncMethods:
    """Tests for sync client method wrappers."""

    @pytest.fixture
    def sync_client(self):
        """Create a sync client for testing."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            requests_per_minute=None,
        )
        yield client
        client.close()

    def test_get_returns_dataframe(self, sync_client):
        """get() returns a Polars DataFrame."""
        mock_df = pl.DataFrame({"No": ["C1", "C2"]})
        with patch.object(sync_client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = sync_client.get("customers")

        assert isinstance(result, pl.DataFrame)
        assert len(result) == 2
        mock_get.assert_called_once()

    def test_get_passes_parameters(self, sync_client):
        """get() passes all parameters to async client."""
        from odyn.query import ODataQuery

        mock_df = pl.DataFrame()
        query = ODataQuery().top(10)

        with patch.object(sync_client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            sync_client.get(
                "customers",
                query=query,
                paginate=False,
                use_cache=False,
            )

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["query"] is query
        assert call_kwargs["paginate"] is False
        assert call_kwargs["use_cache"] is False

    def test_get_by_key_returns_dict(self, sync_client):
        """get_by_key() returns a dictionary."""
        mock_record = {"No": "C001", "Name": "Customer 1"}
        with patch.object(sync_client._client, "get_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_record
            result = sync_client.get_by_key("customers", "C001")

        assert result == mock_record

    def test_get_by_id_returns_dict(self, sync_client):
        """get_by_id() returns a dictionary."""
        mock_record = {"No": "C001", "SystemId": "abc-123"}
        with patch.object(sync_client._client, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_record
            result = sync_client.get_by_id("customers", "abc-123")

        assert result == mock_record

    def test_count_returns_int(self, sync_client):
        """count() returns an integer."""
        with patch.object(sync_client._client, "count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 42
            result = sync_client.count("customers")

        assert result == 42

    def test_get_endpoints_returns_list(self, sync_client):
        """get_endpoints() returns a list of strings."""
        with patch.object(sync_client._client, "get_endpoints", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ["customers", "vendors", "items"]
            result = sync_client.get_endpoints()

        assert result == ["customers", "vendors", "items"]

    def test_get_first_returns_dict_or_none(self, sync_client):
        """get_first() returns a dictionary or None."""
        mock_record = {"No": "C001"}
        with patch.object(sync_client._client, "get_first", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_record
            result = sync_client.get_first("customers")

        assert result == mock_record

    def test_exists_returns_bool(self, sync_client):
        """exists() returns a boolean."""
        with patch.object(sync_client._client, "exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True
            result = sync_client.exists("customers", "C001")

        assert result is True

    def test_get_since_returns_dataframe(self, sync_client):
        """get_since() returns a Polars DataFrame."""
        mock_df = pl.DataFrame({"No": ["C1"]})
        with patch.object(sync_client._client, "get_since", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = sync_client.get_since("customers", "2024-01-15T00:00:00Z")

        assert isinstance(result, pl.DataFrame)

    def test_get_before_returns_dataframe(self, sync_client):
        """get_before() returns a Polars DataFrame."""
        mock_df = pl.DataFrame({"No": ["C1"]})
        with patch.object(sync_client._client, "get_before", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = sync_client.get_before("customers", "2024-01-15T00:00:00Z")

        assert isinstance(result, pl.DataFrame)

    def test_get_all_returns_dataframe(self, sync_client):
        """get_all() returns a Polars DataFrame."""
        mock_df = pl.DataFrame({"No": ["C1", "C2"]})
        with patch.object(sync_client._client, "get_all", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = sync_client.get_all("customers")

        assert isinstance(result, pl.DataFrame)

    def test_get_batch_returns_dataframe(self, sync_client):
        """get_batch() returns a Polars DataFrame."""
        mock_df = pl.DataFrame({"No": ["C1", "C2"]})
        with patch.object(sync_client._client, "get_batch", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = sync_client.get_batch("customers", "No", ["C1", "C2"])

        assert isinstance(result, pl.DataFrame)


class TestBCWebServiceClientSyncCacheMethods:
    """Tests for sync client cache methods."""

    @pytest.fixture
    def sync_client(self):
        """Create a sync client for testing."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )
        yield client
        client.close()

    def test_clear_cache_returns_int(self, sync_client):
        """clear_cache() returns number of cleared entries."""
        sync_client._client.cache = MagicMock()
        sync_client._client.cache.clear.return_value = 5

        result = sync_client.clear_cache()
        assert result == 5

    def test_cleanup_cache_returns_int(self, sync_client):
        """cleanup_cache() returns number of removed entries."""
        sync_client._client.cache = MagicMock()
        sync_client._client.cache.cleanup.return_value = 3

        result = sync_client.cleanup_cache()
        assert result == 3

    def test_cache_size_property(self, sync_client):
        """cache_size returns the cache size."""
        sync_client._client.cache = MagicMock()
        sync_client._client.cache.size.return_value = 10

        assert sync_client.cache_size == 10

    def test_cache_stats_property(self, sync_client):
        """cache_stats returns cache statistics."""
        sync_client._client.cache = MagicMock()
        sync_client._client.cache.stats.return_value = {"hits": 5, "misses": 2}

        assert sync_client.cache_stats == {"hits": 5, "misses": 2}


class TestBCWebServiceClientSyncContextManager:
    """Tests for context manager support."""

    def test_context_manager_entry(self):
        """__enter__ returns self."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )
        with client as ctx:
            assert ctx is client

    def test_context_manager_exit_closes_client(self):
        """__exit__ closes the client."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )
        # Start the loop so close() has something to clean up
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pl.DataFrame()
            with client:
                client.get("test")
                assert client._loop is not None
        # After exit, loop should be cleaned up
        assert client._loop is None

    def test_repr(self):
        """__repr__ returns a string representation."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )
        repr_str = repr(client)
        assert "BCWebServiceClientSync" in repr_str
        assert "wrapping" in repr_str
        client.close()


class TestBCWebServiceClientSyncIntegration:
    """Integration tests for sync client with real async operations."""

    def test_sync_client_runs_async_operations(self):
        """Sync client correctly runs async operations."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            requests_per_minute=None,
        )

        # Patch at the HTTP level to verify async execution
        mock_df = pl.DataFrame({"No": ["C1"]})
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = client.get("customers")

        assert isinstance(result, pl.DataFrame)
        assert len(result) == 1
        client.close()

    def test_multiple_sync_calls_reuse_loop(self):
        """Multiple sync calls reuse the same event loop."""
        client = BCWebServiceClientSync.create(
            server="https://bc-server:7048",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            requests_per_minute=None,
        )

        mock_df = pl.DataFrame({"No": ["C1"]})
        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df

            # First call starts the loop
            client.get("customers")
            loop1 = client._loop

            # Second call should reuse the same loop
            client.get("customers")
            loop2 = client._loop

        assert loop1 is loop2
        client.close()
