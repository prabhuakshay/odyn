"""Tests for retry, rate limiting, and concurrency features.

This module tests the resilience features of BCWebServiceClient:
- Retry logic with exponential backoff
- Rate limiting
- Concurrent request limits
- Exception handling for retryable errors
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from odyn.auth import BasicAuth
from odyn.client import BCWebServiceClient
from odyn.exceptions import (
    AuthenticationError,
    ConnectionError as OdynConnection,
    NotFoundError,
    RateLimitError,
    RetryExhaustedError,
    ServerError,
    TimeoutError as OdynTimeout,
    ValidationError,
)


class TestClientResilienceConfig:
    """Tests for resilience configuration options."""

    def test_create_default_max_retries(self):
        """create() uses default max_retries of 3."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.max_retries == 3

    def test_create_custom_max_retries(self):
        """create() accepts custom max_retries."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=5,
        )
        assert client.max_retries == 5

    def test_create_default_retry_backoff(self):
        """create() uses default retry_backoff of 1.0."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.retry_backoff == 1.0

    def test_create_custom_retry_backoff(self):
        """create() accepts custom retry_backoff."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            retry_backoff=0.5,
        )
        assert client.retry_backoff == 0.5

    def test_create_default_max_connections(self):
        """create() uses default max_connections of 4."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.max_connections == 4

    def test_create_custom_max_connections(self):
        """create() accepts custom max_connections."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_connections=10,
        )
        assert client.max_connections == 10

    def test_create_default_rate_limit(self):
        """create() uses default rate_limit of 550.0 requests per minute."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        assert client.rate_limit == 550.0

    def test_create_custom_rate_limit(self):
        """create() accepts custom rate_limit."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=300.0,
        )
        assert client.rate_limit == 300.0

    def test_create_disable_rate_limit(self):
        """create() can disable rate limiting with None."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,
        )
        assert client.rate_limit is None

    def test_create_zero_retries(self):
        """create() allows disabling retries with 0."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=0,
        )
        assert client.max_retries == 0


class TestBackoffCalculation:
    """Tests for exponential backoff calculation."""

    def test_calculate_backoff_uses_retry_after_if_provided(self):
        """_calculate_backoff uses retry_after when provided."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        backoff = client._calculate_backoff(0, retry_after=5.0)
        assert backoff == 5.0

    def test_calculate_backoff_exponential_growth(self):
        """_calculate_backoff grows exponentially."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            retry_backoff=1.0,
        )

        # Get backoffs for multiple attempts
        backoffs = []
        for attempt in range(4):
            with patch("random.uniform", return_value=0):  # Remove jitter for testing
                backoffs.append(client._calculate_backoff(attempt))

        # Should be 1, 2, 4, 8 (2^n pattern)
        assert backoffs[0] == 1.0
        assert backoffs[1] == 2.0
        assert backoffs[2] == 4.0
        assert backoffs[3] == 8.0

    def test_calculate_backoff_includes_jitter(self):
        """_calculate_backoff adds jitter to prevent thundering herd."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            retry_backoff=1.0,
        )

        # With jitter, backoff should be in range [base, base + retry_backoff]
        with patch("random.uniform", return_value=0.5):
            backoff = client._calculate_backoff(0)

        assert backoff == 1.5  # 1.0 base + 0.5 jitter


class TestRetryableExceptions:
    """Tests for the _is_retryable method."""

    def test_timeout_error_is_retryable(self):
        """TimeoutError is retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = OdynTimeout("timeout", url="http://test")
        assert client._is_retryable(exc) is True

    def test_connection_error_is_retryable(self):
        """ConnectionError is retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = OdynConnection("connection failed", url="http://test")
        assert client._is_retryable(exc) is True

    def test_rate_limit_error_is_retryable(self):
        """RateLimitError is retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = RateLimitError(message="rate limited", status_code=429, url="http://test")
        assert client._is_retryable(exc) is True

    def test_server_error_is_retryable(self):
        """ServerError (5xx) is retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = ServerError(message="server error", status_code=500, url="http://test")
        assert client._is_retryable(exc) is True

    def test_authentication_error_not_retryable(self):
        """AuthenticationError is not retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = AuthenticationError(message="unauthorized", status_code=401)
        assert client._is_retryable(exc) is False

    def test_validation_error_not_retryable(self):
        """ValidationError is not retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = ValidationError(message="bad request", status_code=400)
        assert client._is_retryable(exc) is False

    def test_not_found_error_not_retryable(self):
        """NotFoundError is not retryable."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )
        exc = NotFoundError(message="not found", status_code=404)
        assert client._is_retryable(exc) is False


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_creation(self):
        """RateLimitError can be created with retry_after."""
        exc = RateLimitError(
            message="Too many requests",
            status_code=429,
            url="http://test",
            retry_after=5.0,
        )
        assert exc.message == "Too many requests"
        assert exc.status_code == 429
        assert exc.retry_after == 5.0

    def test_rate_limit_error_default_retry_after(self):
        """RateLimitError has None retry_after by default."""
        exc = RateLimitError(
            message="Too many requests",
            status_code=429,
        )
        assert exc.retry_after is None


class TestRetryExhaustedError:
    """Tests for RetryExhaustedError exception."""

    def test_retry_exhausted_error_creation(self):
        """RetryExhaustedError stores attempt count and last exception."""
        last_exc = ServerError(message="server error", status_code=500)
        exc = RetryExhaustedError(
            "Request failed",
            attempts=3,
            last_exception=last_exc,
        )
        assert exc.attempts == 3
        assert exc.last_exception is last_exc
        assert "Request failed" in str(exc)


class TestRetryBehavior:
    """Tests for retry behavior in requests."""

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self):
        """Successful request doesn't trigger retry."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,  # Disable rate limiting for test speed
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_response.content = b"{}"

        with patch.object(client._http, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client._request("GET", "http://test")

        assert mock_request.call_count == 1
        assert result == {"value": []}

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Request retries on timeout error."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=2,
            retry_backoff=0.01,  # Fast backoff for testing
            rate_limit=None,
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_response.content = b"{}"

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            return mock_response

        with patch.object(client._http, "request", side_effect=mock_request):
            result = await client._request("GET", "http://test")

        assert call_count == 3  # 2 failures + 1 success
        assert result == {"value": []}

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(self):
        """Exhausted retries raise RetryExhaustedError."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=2,
            retry_backoff=0.01,
            rate_limit=None,
        )

        async def mock_request(*args, **kwargs):
            raise httpx.TimeoutException("timeout")

        with (
            patch.object(client._http, "request", side_effect=mock_request),
            pytest.raises(RetryExhaustedError) as exc_info,
        ):
            await client._request("GET", "http://test")

        assert exc_info.value.attempts == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self):
        """AuthenticationError doesn't trigger retry."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=3,
            rate_limit=None,
        )

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json.return_value = {}
        mock_response.reason_phrase = "Unauthorized"
        mock_response.content = b"{}"

        with patch.object(client._http, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            with pytest.raises(AuthenticationError):
                await client._request("GET", "http://test")

        # Should only be called once (no retry)
        assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Request retries on 5xx server error."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=2,
            retry_backoff=0.01,
            rate_limit=None,
        )

        call_count = 0

        def create_response(status_code):
            mock = MagicMock()
            mock.is_success = status_code < 400
            mock.status_code = status_code
            mock.text = "OK" if status_code < 400 else "Error"
            mock.json.return_value = {"value": []} if status_code < 400 else {"error": {}}
            mock.reason_phrase = "OK" if status_code < 400 else "Error"
            mock.content = b"{}"
            return mock

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return create_response(500)
            return create_response(200)

        with patch.object(client._http, "request", side_effect=mock_request):
            result = await client._request("GET", "http://test")

        assert call_count == 3
        assert result == {"value": []}

    @pytest.mark.asyncio
    async def test_retry_with_rate_limit_response(self):
        """Request retries on 429 with Retry-After header."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_retries=2,
            retry_backoff=0.01,
            rate_limit=None,
        )

        call_count = 0

        def create_response(status_code, retry_after=None):
            mock = MagicMock()
            mock.is_success = status_code < 400
            mock.status_code = status_code
            mock.text = "OK" if status_code < 400 else "Too Many Requests"
            mock.json.return_value = {"value": []} if status_code < 400 else {"error": {}}
            mock.reason_phrase = "OK" if status_code < 400 else "Too Many Requests"
            mock.content = b"{}"
            mock.headers = {"Retry-After": str(retry_after)} if retry_after else {}
            return mock

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return create_response(429, retry_after=0.01)
            return create_response(200)

        with patch.object(client._http, "request", side_effect=mock_request):
            result = await client._request("GET", "http://test")

        assert call_count == 2
        assert result == {"value": []}


class TestRateLimiting:
    """Tests for rate limiting behavior using aiolimiter."""

    def test_rate_limiter_initialized_when_enabled(self):
        """Rate limiter is initialized when rate_limit is set."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=600.0,  # 600 req/min
        )
        assert client._limiter is not None
        # AsyncLimiter stores max_rate and time_period
        assert client._limiter.max_rate == 600.0
        assert client._limiter.time_period == 60.0

    def test_rate_limiter_none_when_disabled(self):
        """Rate limiter is None when rate_limit is None."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,
        )
        assert client._limiter is None

    @pytest.mark.asyncio
    async def test_rate_limit_acquires_token(self):
        """Rate limiting acquires a token from the limiter."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=600.0,  # 600 req/min = 10 req/s
        )

        with patch.object(client._limiter, "acquire", new_callable=AsyncMock) as mock_acquire:
            await client._apply_rate_limit()

        mock_acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_skips_acquire(self):
        """Disabled rate limiting doesn't acquire any token."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,
        )

        # No limiter should exist
        assert client._limiter is None

        # Calling _apply_rate_limit should be a no-op
        # It should complete immediately without error
        await client._apply_rate_limit()


class TestConcurrencyLimits:
    """Tests for concurrent connection limits."""

    def test_semaphore_initialized_with_max_connections(self):
        """Semaphore is initialized with max_connections value."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_connections=7,
        )
        # Semaphore's initial value should be max_connections
        assert client._semaphore._value == 7

    def test_httpx_limits_set_correctly(self):
        """httpx client limits are set correctly."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            max_connections=8,
        )
        # Check that the client's max_connections config is stored
        assert client.max_connections == 8
        # The httpx client uses this for connection pooling
        # We can verify the pool limits via the transport
        transport = client._http._transport
        pool = transport._pool
        assert pool._max_connections == 8


class TestGetBatch:
    """Tests for the get_batch helper method."""

    @pytest.mark.asyncio
    async def test_get_batch_empty_values_raises_error(self):
        """get_batch raises ValueError for empty values list."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
        )

        with pytest.raises(ValueError, match="values list cannot be empty"):
            await client.get_batch("customers", "No", [])

    @pytest.mark.asyncio
    async def test_get_batch_chunks_values(self):
        """get_batch splits values into batches and makes concurrent requests."""
        import polars as pl

        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,  # Disable for test speed
        )

        # Create mock response
        mock_df = pl.DataFrame({"No": ["C001", "C002"], "Name": ["Test1", "Test2"]})

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_df

        with patch.object(client, "get", side_effect=mock_get):
            # 5 values with batch_size=2 should create 3 batches
            result = await client.get_batch(
                "customers",
                "No",
                ["C001", "C002", "C003", "C004", "C005"],
                batch_size=2,
            )

        # Should have made 3 concurrent requests
        assert call_count == 3
        # Result should be combined DataFrame
        assert len(result) == 6  # 3 batches * 2 rows each

    @pytest.mark.asyncio
    async def test_get_batch_with_select(self):
        """get_batch passes select parameter to queries."""
        import polars as pl

        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,
        )

        mock_df = pl.DataFrame({"No": ["C001"], "Name": ["Test"]})
        captured_queries = []

        async def mock_get(endpoint, *, query=None, **kwargs):
            if query:
                captured_queries.append(query.build())
            return mock_df

        with patch.object(client, "get", side_effect=mock_get):
            await client.get_batch(
                "customers",
                "No",
                ["C001"],
                select=["No", "Name", "Balance"],
            )

        assert len(captured_queries) == 1
        assert "$select" in captured_queries[0]
        assert "No,Name,Balance" in captured_queries[0]["$select"]

    @pytest.mark.asyncio
    async def test_get_batch_fail_fast_false_continues_on_error(self):
        """get_batch continues processing when fail_fast=False."""
        import polars as pl

        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,
        )

        call_count = 0
        mock_df = pl.DataFrame({"No": ["C001"]})

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ServerError(message="Server error", status_code=500)
            return mock_df

        with patch.object(client, "get", side_effect=mock_get):
            result = await client.get_batch(
                "customers",
                "No",
                ["C001", "C002", "C003"],
                batch_size=1,
                fail_fast=False,
            )

        # Should have processed all 3 batches
        assert call_count == 3
        # 2 successful batches
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_batch_fail_fast_true_raises_immediately(self):
        """get_batch raises immediately when fail_fast=True."""
        client = BCWebServiceClient.create(
            server="https://bc-server:7048",
            instance="BC210",
            auth=BasicAuth("user", "pass"),
            rate_limit=None,
        )

        async def mock_get(*args, **kwargs):
            raise ServerError(message="Server error", status_code=500)

        with patch.object(client, "get", side_effect=mock_get), pytest.raises(ServerError):
            await client.get_batch(
                "customers",
                "No",
                ["C001", "C002"],
                batch_size=1,
                fail_fast=True,
            )
