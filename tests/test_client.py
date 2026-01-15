"""Tests for the odyn.client module."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import polars as pl
import pytest

from odyn.auth import BasicAuth
from odyn.client import BCWebServiceClient
from odyn.exceptions import (
    NotFoundError,
    RateLimitError,
    ValidationError,
    WebServiceError,
)


class TestBCWebServiceClientCreate:
    """Tests for BCWebServiceClient.create() factory method."""

    def test_create_constructs_correct_base_url(self):
        """create() builds the correct ODataV4 URL."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.base_url == "https://bc-server:7048/BC210/ODataV4"

    def test_create_strips_trailing_slash_from_server(self):
        """create() normalizes server URL by removing trailing slash."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048/",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.base_url == "https://bc-server:7048/BC210/ODataV4"

    def test_create_with_http_server(self):
        """create() works with HTTP (non-SSL) URLs."""
        client = BCWebServiceClient.create(
            server="http://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.base_url == "http://bc-server:7048/BC210/ODataV4"

    def test_create_stores_company(self):
        """create() stores company name."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            company="CRONUS International Ltd.",
        )
        assert client.company == "CRONUS International Ltd."

    def test_create_default_timeout(self):
        """create() uses default timeout of 30 seconds."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.timeout == 30.0

    def test_create_custom_timeout(self):
        """create() accepts custom timeout."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            timeout=60.0,
        )
        assert client.timeout == 60.0

    def test_create_default_max_pages(self):
        """create() uses default max_pages of 100."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.max_pages == 100

    def test_create_custom_max_pages(self):
        """create() accepts custom max_pages."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_pages=50,
        )
        assert client.max_pages == 50

    def test_create_default_verify_ssl(self):
        """create() uses default verify_ssl of True."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.verify_ssl is True

    def test_create_disable_ssl_verification(self):
        """create() can disable SSL verification."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            verify_ssl=False,
        )
        assert client.verify_ssl is False

    def test_create_no_cache_by_default(self):
        """create() does not configure cache by default."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.cache is None

    def test_create_with_cache(self, tmp_path):
        """create() configures cache when cache_dir is provided."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            cache_dir=tmp_path,
            cache_ttl=3600,
        )
        assert client.cache is not None


class TestBCWebServiceClientBuildUrl:
    """Tests for BCWebServiceClient._build_url() method."""

    def test_build_url_without_company(self):
        """_build_url() returns simple URL without company."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        url = client._build_url("customers")
        assert url == "https://bc-server:7048/BC210/ODataV4/customers"

    def test_build_url_with_company(self):
        """_build_url() includes company in URL when set."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            company="CRONUS",
        )
        url = client._build_url("customers")
        assert url == "https://bc-server:7048/BC210/ODataV4/Company('CRONUS')/customers"

    def test_build_url_strips_leading_slash(self):
        """_build_url() strips leading slash from endpoint."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        url = client._build_url("/customers")
        assert url == "https://bc-server:7048/BC210/ODataV4/customers"


class TestBCWebServiceClientRepr:
    """Tests for BCWebServiceClient.__repr__() method."""

    def test_repr_includes_base_url(self):
        """__repr__ includes base_url."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert "https://bc-server:7048/BC210/ODataV4" in repr(client)

    def test_repr_includes_company(self):
        """__repr__ includes company."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            company="CRONUS",
        )
        assert "CRONUS" in repr(client)

    def test_repr_shows_cache_status(self, tmp_path):
        """__repr__ shows cache status."""
        client_no_cache = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert "cache=disabled" in repr(client_no_cache)

        client_with_cache = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            cache_dir=tmp_path,
        )
        assert "cache=enabled" in repr(client_with_cache)


class TestBCWebServiceClientCacheHelpers:
    """Tests for cache helper methods."""

    def test_cache_size_returns_zero_without_cache(self):
        """cache_size returns 0 when no cache is configured."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.cache_size == 0

    def test_clear_cache_returns_zero_without_cache(self):
        """clear_cache returns 0 when no cache is configured."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.clear_cache() == 0

    def test_cleanup_cache_returns_zero_without_cache(self):
        """cleanup_cache returns 0 when no cache is configured."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.cleanup_cache() == 0


class TestBCWebServiceClientResponse:
    """Tests for _handle_response and related error handling."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )

    @pytest.mark.asyncio
    async def test_handle_response_204(self, client):
        """204 No Content returns empty dict."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.status_code = 204

        result = await client._handle_response(mock_response, "http://test")
        assert result == {}

    @pytest.mark.asyncio
    async def test_handle_response_json_error(self, client):
        """Handles invalid JSON in error response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 400
        mock_response.text = "Not JSON"
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.reason_phrase = "Bad Request"

        with pytest.raises(ValidationError) as exc:
            await client._handle_response(mock_response, "http://test")
        assert exc.value.message == "Not JSON"

    @pytest.mark.asyncio
    async def test_handle_response_rate_limit_no_header(self, client):
        """Handles 429 without Retry-After header."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.text = '{"error": {"message": "Too Many"}}'
        mock_response.json.return_value = {"error": {"message": "Too Many"}}

        with pytest.raises(RateLimitError) as exc:
            await client._handle_response(mock_response, "http://test")
        assert exc.value.retry_after is None

    @pytest.mark.asyncio
    async def test_handle_response_unexpected_error(self, client):
        """Handles unexpected error codes."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.is_success = False
        mock_response.status_code = 418  # I'm a teapot
        mock_response.text = "Teapot"
        mock_response.json.side_effect = ValueError()
        mock_response.reason_phrase = "Teapot"

        with pytest.raises(WebServiceError):
            await client._handle_response(mock_response, "http://test")

    def test_extract_error_message_non_dict(self, client):
        """_extract_error_message handles non-dict odata_error."""
        # This covers line 426: return fallback
        assert client._extract_error_message("not a dict", "fallback") == "fallback"


class TestBCWebServiceClientHighLevel:
    """Tests for high-level convenience methods in BCWebServiceClient."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )

    @pytest.mark.asyncio
    async def test_get_all(self, client):
        """get_all calls get with correct query."""
        import polars as pl

        mock_df = pl.DataFrame({"No": ["C001"]})
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = await client.get_all("customers", batch_size=500)

            assert result is mock_df
            mock_get.assert_called_once()
            query = mock_get.call_args[1]["query"]
            assert query._top == 500

    @pytest.mark.asyncio
    async def test_get_first(self, client):
        """get_first returns first row as dict."""
        import polars as pl

        mock_df = pl.DataFrame({"No": ["C001"], "Name": ["John"]})
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = await client.get_first("customers")

            assert result == {"No": "C001", "Name": "John"}

    @pytest.mark.asyncio
    async def test_get_first_empty(self, client):
        """get_first returns None if no records."""
        import polars as pl

        mock_df = pl.DataFrame()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            result = await client.get_first("customers")

            assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(self, client):
        """exists returns True if record found."""
        with patch.object(client, "get_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"SystemId": "abc"}
            assert await client.exists("customers", "C001") is True

    @pytest.mark.asyncio
    async def test_exists_false(self, client):
        """exists returns False if NotFoundError raised."""
        with patch.object(client, "get_by_key", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = NotFoundError("Not found", status_code=404)
            assert await client.exists("customers", "C001") is False

    @pytest.mark.asyncio
    async def test_get_by_id(self, client):
        """get_by_id calls _request with correct URL."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"No": "C001"}
            guid = "12345678-1234-1234-1234-123456789012"
            result = await client.get_by_id("customers", guid, select=["No"])

            assert result == {"No": "C001"}
            mock_request.assert_called_once()
            args = mock_request.call_args
            assert f"customers({guid})" in args[0][1]
            assert args[1]["params"] == {"$select": "No"}

    @pytest.mark.asyncio
    async def test_get_endpoints(self, client):
        """get_endpoints parses service document."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "value": [
                    {"name": "customers", "url": "..."},
                    {"name": "vendors", "url": "..."},
                    {"name": "", "url": "..."},  # Skip empty names
                ]
            }
            endpoints = await client.get_endpoints()
            assert endpoints == ["customers", "vendors"]

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Async context manager closes client."""
        client._http = MagicMock(spec=httpx.AsyncClient)
        client._http.aclose = AsyncMock()

        async with client as c:
            assert c is client

        client._http.aclose.assert_called_once()


class TestBCWebServiceClientPagination:
    """Tests for pagination and streaming logic."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            max_pages=2,
        )

    @pytest.mark.asyncio
    async def test_paginate_multiple_pages(self, client):
        """_paginate follows nextLink."""

        async def mock_fetch_page(url, params=None):
            if "page1" in url or url.endswith("customers"):
                return {"value": [{"No": "C1"}], "@odata.nextLink": "http://bc-server/page2"}
            return {"value": [{"No": "C2"}]}

        with patch.object(client, "_fetch_page", side_effect=mock_fetch_page):
            df = await client._paginate("customers")
            assert len(df) == 2
            assert df["No"].to_list() == ["C1", "C2"]

    @pytest.mark.asyncio
    async def test_paginate_limit_reached(self, client):
        """_paginate stops at max_pages."""

        async def mock_fetch_page(url, params=None):
            return {"value": [{"No": "C"}], "@odata.nextLink": "http://bc-server/next"}

        with patch.object(client, "_fetch_page", side_effect=mock_fetch_page):
            # client.max_pages is set to 2 in fixture
            df = await client._paginate("customers")
            assert len(df) == 2

    @pytest.mark.asyncio
    async def test_paginate_empty(self, client):
        """_paginate returns empty DF if no records."""
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": []}
            df = await client._paginate("customers")
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_get_stream(self, client):
        """get_stream yields pages."""

        async def mock_fetch_page(url, params=None):
            if "page1" in url or url.endswith("customers"):
                return {"value": [{"No": "C1"}], "@odata.nextLink": "http://bc-server/page2"}
            return {"value": [{"No": "C2"}]}

        with patch.object(client, "_fetch_page", side_effect=mock_fetch_page):
            pages = [page async for page in client.get_stream("customers")]

            assert len(pages) == 2
            assert pages[0]["No"][0] == "C1"
            assert pages[1]["No"][0] == "C2"

    @pytest.mark.asyncio
    async def test_count(self, client):
        """count returns integer from $count endpoint."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "42"
            val = await client.count("customers")
            assert val == 42
            assert "/$count" in mock_request.call_args[0][1]

    @pytest.mark.asyncio
    async def test_count_with_filter(self, client):
        """count preserves only $filter param."""
        from odyn.query import F, ODataQuery

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "10"
            query = ODataQuery().filter(F.No == "C1").select("No").top(1)
            await client.count("customers", query=query)

            params = mock_request.call_args[1]["params"]
            assert "$filter" in params
            assert "$select" not in params
            assert "$top" not in params

    @pytest.mark.asyncio
    async def test_count_invalid_response(self, client):
        """count returns 0 if response is not a string."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"not": "a string"}
            assert await client.count("customers") == 0


class TestBCWebServiceClientRequestLogic:
    """Tests for core request logic and error handling in _request."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            requests_per_minute=None,
            max_retries=0,
        )

    @pytest.mark.asyncio
    async def test_request_connect_error(self, client):
        """_request handles httpx.ConnectError."""
        from odyn.exceptions import RetryExhaustedError

        with (
            patch.object(client._http, "request", side_effect=httpx.ConnectError("fail")),
            pytest.raises(RetryExhaustedError),
        ):
            await client._request("GET", "http://test")

    @pytest.mark.asyncio
    async def test_request_ssl_error(self, client):
        """_request handles SSL errors."""
        from odyn.exceptions import SSLError as OdynSSLError

        with (
            patch.object(client._http, "request", side_effect=Exception("SSL error")),
            pytest.raises(OdynSSLError),
        ):
            await client._request("GET", "http://test")

    @pytest.mark.asyncio
    async def test_request_generic_error(self, client):
        """_request re-raises non-retryable generic errors."""
        with (
            patch.object(client._http, "request", side_effect=RuntimeError("generic")),
            pytest.raises(RuntimeError, match="generic"),
        ):
            await client._request("GET", "http://test")

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, client, tmp_path):
        """get returns cached result if available."""
        import polars as pl

        client.cache = MagicMock()
        mock_df = pl.DataFrame({"No": ["C1"]})
        client.cache.get.return_value = mock_df

        result = await client.get("customers", use_cache=True)
        assert result is mock_df
        client.cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_page_no_paginate(self, client):
        """get(paginate=False) fetches single page."""
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": [{"No": "C1"}]}
            df = await client.get("customers", paginate=False)
            assert len(df) == 1
            assert df["No"][0] == "C1"

    @pytest.mark.asyncio
    async def test_get_page_no_paginate_empty(self, client):
        """get(paginate=False) handles empty results."""
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": []}
            df = await client.get("customers", paginate=False)
            assert df.is_empty()


class TestBCWebServiceClientBatchOptions:
    """Tests for get_batch options (expand, additional_filter, etc)."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            requests_per_minute=None,
        )

    @pytest.mark.asyncio
    async def test_get_batch_full_options(self, client):
        """get_batch handles expand, order_by, additional_filter."""
        import polars as pl

        from odyn.query import F

        mock_df = pl.DataFrame({"No": ["C1"]})
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            await client.get_batch(
                "customers",
                "No",
                ["C1"],
                expand=["ShipToAddress"],
                order_by=["Name desc"],
                additional_filter=(F.Blocked == False),  # noqa: E712
            )

            mock_get.assert_called_once()
            query = mock_get.call_args[1]["query"]
            assert "ShipToAddress" in query._expand
            assert "Name desc" in query._order_by
            params = query.build()
            assert "Blocked eq false" in params["$filter"]

    @pytest.mark.asyncio
    async def test_get_batch_handles_exceptions(self, client):
        """get_batch handles exceptions for individual batches when fail_fast=False."""
        import polars as pl

        mock_df = pl.DataFrame({"No": ["C1"]})

        async def mock_get(*args, **kwargs):
            if "C2" in str(kwargs.get("query")):
                raise RuntimeError("Batch failed")
            return mock_df

        with patch.object(client, "get", side_effect=mock_get):
            # 2 batches
            result = await client.get_batch("customers", "No", ["C1", "C2"], batch_size=1, fail_fast=False)
            assert len(result) == 1  # Only one batch succeeded

    @pytest.mark.asyncio
    async def test_get_batch_all_failed(self, client):
        """get_batch returns empty DF if all batches fail."""
        with patch.object(client, "get", side_effect=RuntimeError("fail")):
            result = await client.get_batch("customers", "No", ["C1"], fail_fast=False)
            assert result.is_empty()

    @pytest.mark.asyncio
    async def test_paginate_stream_exit_by_limit(self, client):
        """_paginate_stream exit by max_pages limit."""
        client.max_pages = 1
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": [{"No": "C1"}], "@odata.nextLink": "http://bc-server/page2"}
            pages = [page async for page in client._paginate_stream("http://test")]
            assert len(pages) == 1


class TestBCWebServiceClientMisc:
    """Tests for remaining miscellaneous client logic."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
        )

    def test_configure_logging_custom_format(self):
        """_configure_logging with custom format."""
        from odyn.client import _configure_logging

        _configure_logging(logging.DEBUG, format_string="%(message)s")
        # Just verifying it doesn't crash as we can't easily check side-effects on global loggers

    @pytest.mark.asyncio
    async def test_get_by_key_no_select(self, client):
        """get_by_key without select."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"No": "C1"}
            await client.get_by_key("customers", "C1")
            assert mock_request.call_args[1]["params"] is None

    @pytest.mark.asyncio
    async def test_get_by_key_with_select(self, client):
        """get_by_key with select."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"No": "C1"}
            await client.get_by_key("customers", "C1", select=["No", "Name"])
            assert mock_request.call_args[1]["params"] == {"$select": "No,Name"}

    @pytest.mark.asyncio
    async def test_apply_rate_limit_not_triggered(self, client):
        """_apply_rate_limit is a no-op when limiter is None."""
        client.requests_per_minute = None
        client._limiter = None

        # Should complete immediately without error
        await client._apply_rate_limit()

    @pytest.mark.asyncio
    async def test_get_by_id_no_select(self, client):
        """get_by_id without select."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"No": "C1"}
            await client.get_by_id("customers", "id")
            assert mock_request.call_args[1]["params"] is None

    @pytest.mark.asyncio
    async def test_fetch_page_coverage(self, client):
        """_fetch_page calls _request."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            await client._fetch_page("http://test")
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_paginate_stream_no_records(self, client):
        """_paginate_stream handles empty results."""
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": []}
            pages = [page async for page in client._paginate_stream("customers")]
            assert len(pages) == 0

    @pytest.mark.asyncio
    async def test_get_no_cache_available(self, client):
        """get when cache is None."""
        client.cache = None
        with patch.object(client, "_paginate", new_callable=AsyncMock) as mock_paginate:
            mock_paginate.return_value = pl.DataFrame({"No": ["C1"]})
            await client.get("customers", use_cache=True)
            # Should just work

    @pytest.mark.asyncio
    async def test_get_cache_miss_and_store(self, client, tmp_path):
        """get handles cache miss and stores result."""
        client.cache = MagicMock()
        client.cache.get.return_value = None

        mock_df = pl.DataFrame({"No": ["C1"]})
        with patch.object(client, "_paginate", new_callable=AsyncMock) as mock_paginate:
            mock_paginate.return_value = mock_df
            await client.get("customers", use_cache=True)

            client.cache.get.assert_called_once()
            client.cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_no_paginate_one_record(self, client):
        """get(paginate=False) with one record."""
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": [{"No": "C1"}]}
            df = await client.get("customers", paginate=False)
            assert not df.is_empty()

    @pytest.mark.asyncio
    async def test_get_no_paginate_no_records(self, client):
        """get(paginate=False) with no records."""
        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": []}
            df = await client.get("customers", paginate=False)
            assert df.is_empty()

    def test_clear_and_cleanup_cache_with_cache(self, client):
        """clear_cache and cleanup_cache call cache methods."""
        client.cache = MagicMock()
        client.cache.clear.return_value = 5
        client.cache.cleanup.return_value = 3

        assert client.clear_cache() == 5
        assert client.cleanup_cache() == 3

    def test_cache_size_with_cache(self, client):
        """cache_size calls cache.size()."""
        client.cache = MagicMock()
        client.cache.size.return_value = 10
        assert client.cache_size == 10


class TestProgressCallbacks:
    """Tests for progress callback support in pagination and batch methods."""

    @pytest.fixture
    def client(self):
        return BCWebServiceClient.create(
            server="https://bc-server",
            instance="BC",
            auth=BasicAuth("user", "pass"),
            max_pages=10,
            requests_per_minute=None,
        )

    @pytest.mark.asyncio
    async def test_paginate_calls_progress_callback(self, client):
        """_paginate invokes progress callback for each page."""
        progress_calls = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            progress_calls.append(
                {
                    "page": page,
                    "records_on_page": records_on_page,
                    "total_records": total_records,
                    "is_final": is_final,
                }
            )

        async def mock_fetch_page(url, params=None):
            if "page2" in url:
                return {"value": [{"No": "C2"}]}
            return {"value": [{"No": "C1"}], "@odata.nextLink": "http://bc-server/page2"}

        with patch.object(client, "_fetch_page", side_effect=mock_fetch_page):
            await client._paginate("http://test", on_progress=on_progress)

        assert len(progress_calls) == 2
        assert progress_calls[0] == {
            "page": 1,
            "records_on_page": 1,
            "total_records": 1,
            "is_final": False,
        }
        assert progress_calls[1] == {
            "page": 2,
            "records_on_page": 1,
            "total_records": 2,
            "is_final": True,
        }

    @pytest.mark.asyncio
    async def test_paginate_progress_callback_final_on_max_pages(self, client):
        """_paginate sets is_final=True when max_pages is reached."""
        client.max_pages = 2
        progress_calls = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            progress_calls.append({"page": page, "is_final": is_final})

        async def mock_fetch_page(url, params=None):
            return {"value": [{"No": "C"}], "@odata.nextLink": "http://bc-server/next"}

        with patch.object(client, "_fetch_page", side_effect=mock_fetch_page):
            await client._paginate("http://test", on_progress=on_progress)

        assert len(progress_calls) == 2
        assert progress_calls[0]["is_final"] is False
        assert progress_calls[1]["is_final"] is True

    @pytest.mark.asyncio
    async def test_paginate_stream_calls_progress_callback(self, client):
        """_paginate_stream invokes progress callback for each page."""
        progress_calls = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            progress_calls.append(
                {
                    "page": page,
                    "records_on_page": records_on_page,
                    "total_records": total_records,
                    "is_final": is_final,
                }
            )

        async def mock_fetch_page(url, params=None):
            if "page2" in url:
                return {"value": [{"No": "C2"}, {"No": "C3"}]}
            return {"value": [{"No": "C1"}], "@odata.nextLink": "http://bc-server/page2"}

        with patch.object(client, "_fetch_page", side_effect=mock_fetch_page):
            pages = [page async for page in client._paginate_stream("http://test", on_progress=on_progress)]

        assert len(pages) == 2
        assert len(progress_calls) == 2
        assert progress_calls[0] == {
            "page": 1,
            "records_on_page": 1,
            "total_records": 1,
            "is_final": False,
        }
        assert progress_calls[1] == {
            "page": 2,
            "records_on_page": 2,
            "total_records": 3,
            "is_final": True,
        }

    @pytest.mark.asyncio
    async def test_get_passes_progress_to_paginate(self, client):
        """get() passes on_progress to _paginate."""
        callback_invoked = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            callback_invoked.append(page)

        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": [{"No": "C1"}]}
            await client.get("customers", on_progress=on_progress)

        assert callback_invoked == [1]

    @pytest.mark.asyncio
    async def test_get_no_paginate_calls_progress_once(self, client):
        """get(paginate=False) still invokes progress callback."""
        progress_calls = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            progress_calls.append(
                {
                    "page": page,
                    "records_on_page": records_on_page,
                    "total_records": total_records,
                    "is_final": is_final,
                }
            )

        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": [{"No": "C1"}, {"No": "C2"}]}
            await client.get("customers", paginate=False, on_progress=on_progress)

        assert len(progress_calls) == 1
        assert progress_calls[0] == {
            "page": 1,
            "records_on_page": 2,
            "total_records": 2,
            "is_final": True,
        }

    @pytest.mark.asyncio
    async def test_get_stream_passes_progress_callback(self, client):
        """get_stream() passes on_progress to _paginate_stream."""
        callback_invoked = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            callback_invoked.append(page)

        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": [{"No": "C1"}]}
            pages = [p async for p in client.get_stream("customers", on_progress=on_progress)]

        assert callback_invoked == [1]
        assert len(pages) == 1

    @pytest.mark.asyncio
    async def test_get_batch_calls_batch_progress_callback(self, client):
        """get_batch() invokes BatchProgressCallback for each batch."""
        progress_calls = []

        def on_progress(*, batch, total_batches, successful, failed, is_final):
            progress_calls.append(
                {
                    "batch": batch,
                    "total_batches": total_batches,
                    "successful": successful,
                    "failed": failed,
                    "is_final": is_final,
                }
            )

        mock_df = pl.DataFrame({"No": ["C1"]})

        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_df
            await client.get_batch("customers", "No", ["C1", "C2", "C3"], batch_size=1, on_progress=on_progress)

        # All 3 batches should trigger callbacks
        assert len(progress_calls) == 3
        # Due to concurrent execution, the order may vary, but final state should be correct
        final_call = next(c for c in progress_calls if c["is_final"])
        assert final_call["successful"] == 3
        assert final_call["failed"] == 0
        assert final_call["total_batches"] == 3

    @pytest.mark.asyncio
    async def test_get_batch_progress_tracks_failures(self, client):
        """get_batch() progress callback tracks failed batches."""
        progress_calls = []

        def on_progress(*, batch, total_batches, successful, failed, is_final):
            progress_calls.append(
                {
                    "batch": batch,
                    "successful": successful,
                    "failed": failed,
                    "is_final": is_final,
                }
            )

        mock_df = pl.DataFrame({"No": ["C1"]})

        async def mock_get(*args, **kwargs):
            query_str = str(kwargs.get("query", ""))
            if "'C2'" in query_str:
                raise RuntimeError("Batch failed")
            return mock_df

        with patch.object(client, "get", side_effect=mock_get):
            await client.get_batch(
                "customers", "No", ["C1", "C2", "C3"], batch_size=1, fail_fast=False, on_progress=on_progress
            )

        # Final call should show 1 failure
        final_call = next(c for c in progress_calls if c["is_final"])
        assert final_call["successful"] == 2
        assert final_call["failed"] == 1

    @pytest.mark.asyncio
    async def test_paginate_empty_still_calls_progress(self, client):
        """_paginate still calls progress even for empty pages."""
        progress_calls = []

        def on_progress(*, page, records_on_page, total_records, is_final):
            progress_calls.append({"page": page, "records_on_page": records_on_page})

        with patch.object(client, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"value": []}
            await client._paginate("http://test", on_progress=on_progress)

        assert len(progress_calls) == 1
        assert progress_calls[0] == {"page": 1, "records_on_page": 0}
