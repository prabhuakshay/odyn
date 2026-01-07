"""Tests for the odyn.client module."""

from odyn.auth import BasicAuth
from odyn.client import BCWebServiceClient


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
