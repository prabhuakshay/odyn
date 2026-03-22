# Testing Patterns

**Analysis Date:** 2026-03-22

## Test Framework

**Runner:**
- pytest 9.0.2+
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- asyncio_mode: "auto" (automatic async fixture management)
- asyncio_default_fixture_loop_scope: "function" (fresh loop per test)

**Assertion Library:**
- Built-in pytest assertions

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output (default in config)
pytest --cov=src/odyn          # With coverage report
pytest -m "not slow"            # Exclude slow tests
pytest tests/test_client.py::TestBCWebServiceClientCreate::test_create_constructs_correct_base_url  # Single test
```

**Additional Plugins:**
- pytest-asyncio 1.3.0+ for async test support
- pytest-cov 7.0.0+ for coverage reports

## Test File Organization

**Location:**
- Co-located with source: `tests/` directory mirrors `src/odyn/` structure
- Example: `src/odyn/query/builder.py` → `tests/query/test_builder.py`

**Naming:**
- Test modules: `test_*.py` prefix convention
- Test classes: `Test*` prefix (e.g., `TestBCWebServiceClientCreate`, `TestSelectMethod`)
- Test functions: `test_*` prefix with descriptive names

**Structure:**
```
tests/
├── __init__.py
├── test_auth.py                 # Authentication tests
├── test_cache.py                # Cache tests
├── test_client.py               # Client tests
├── test_exceptions.py           # Exception handling tests
├── test_resilience.py           # Retry/rate-limit/concurrency tests
├── test_sync.py                 # Sync wrapper tests
└── query/
    ├── __init__.py
    ├── test_builder.py          # ODataQuery builder tests
    ├── test_expressions.py      # Filter expression tests
    ├── test_fields.py           # Field factory tests
    └── test_types.py            # Type validation tests
```

Total: ~6,393 test lines across 11 test files

## Test Structure

**Suite Organization:**
```python
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
        # ...test body...
```

**Patterns:**
- Each test is a single focused assertion
- Docstring as test description (shown in `-v` output)
- Arrange-Act-Assert structure (setup, execute, verify)
- Test classes group related tests by feature/method

**Class-based Organization:**
- Group tests by class method or functionality
- Example: `TestODataQueryCreation`, `TestSelectMethod`, `TestFilterMethod`
- Enables shared setup via `setup_method()` if needed

## Mocking

**Framework:** `unittest.mock` (built-in)
- `AsyncMock` for async functions
- `MagicMock` for regular mocks
- `patch()` context manager for temporary mocking

**Patterns:**
```python
from unittest.mock import AsyncMock, MagicMock, patch

# Example: Mock an async HTTP request
@pytest.mark.asyncio
async def test_get_with_mock_response():
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, json=AsyncMock(return_value=[...]))
        # test code
```

**What to Mock:**
- External HTTP requests (httpx calls)
- File I/O for cache operations (to avoid disk writes in unit tests)
- Time-dependent operations (time.time() for TTL tests)
- System dependencies when testing error scenarios

**What NOT to Mock:**
- Core query builder logic (test actual OData generation)
- Exception classes (test actual exception behavior)
- Dataclass properties and methods
- Validation logic (test real validation, not mocked validation)

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def sample_auth():
    """Return a BasicAuth instance for testing."""
    return BasicAuth("user", "password123")

@pytest.fixture
def sample_dataframe():
    """Return a sample Polars DataFrame."""
    return pl.DataFrame({
        "No": ["C001", "C002"],
        "Name": ["Customer A", "Customer B"],
        "Balance": [1000.0, 2500.0],
    })
```

**Location:**
- `tests/conftest.py` for shared fixtures (if needed - check if file exists)
- Individual test files for test-specific fixtures
- Inline factory functions for simple test data

**Common Patterns:**
- Parametrized fixtures: `@pytest.fixture(params=[...])`
- Parametrized tests: `@pytest.mark.parametrize("field_name", ["Name", "Balance", ...])`

**Example Parametrization:**
```python
@pytest.mark.parametrize(
    "field_name",
    ["Name", "CustomerName", "Posting_Date", "Address2"],
    ids=["simple", "compound", "underscore", "with_number"],
)
def test_select_accepts_valid_field_names(self, field_name: str) -> None:
    """Validate that select() accepts various valid field name formats."""
    query = ODataQuery().select(field_name)
    result = query.build()
    assert result["$select"] == field_name
```

## Coverage

**Requirements:**
- Branch coverage enabled (branch = true in [tool.coverage.run])
- Source: `src/odyn` (excludes tests and __init__.py)
- Reports: terminal-missing + HTML

**View Coverage:**
```bash
pytest --cov=src/odyn --cov-report=term-missing
pytest --cov=src/odyn --cov-report=html  # Generates htmlcov/
```

**Excluded from Coverage:**
- `pragma: no cover` comments
- `def __repr__` methods
- `raise NotImplementedError` (abstract methods)
- `if TYPE_CHECKING:` blocks
- `if __name__ == "__main__":` blocks
- `@abstractmethod` decorated methods

## Test Types

**Unit Tests:**
- Scope: Individual functions, methods, classes
- Approach: Test behavior in isolation with mocks for dependencies
- Examples: `test_auth.py` (BasicAuth functionality), `tests/query/test_builder.py` (ODataQuery methods)
- Default marker: None (all tests run by default)

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Real HTTP calls, file I/O, or component composition
- Marker: `@pytest.mark.integration` (can exclude with `-m "not integration"`)
- Example: Tests that use real httpx responses or full client flow

**Async Tests:**
- Scope: Coroutines and async context managers
- Approach: Mark with `@pytest.mark.asyncio`
- Framework: pytest-asyncio with auto mode
- Example: `test_resilience.py` tests for retry logic

**Slow Tests:**
- Scope: Tests with significant setup/teardown or time-dependent logic
- Marker: `@pytest.mark.slow`
- Usage: `pytest -m "not slow"` to skip during development

**Example Async Test:**
```python
class TestClientRetry:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test that client retries on timeout errors."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = TimeoutError("Request timeout")
            # test code
```

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_get_returns_dataframe():
    """get() returns a Polars DataFrame."""
    async with BCWebServiceClient.create(...) as client:
        with patch('httpx.AsyncClient.request') as mock_req:
            mock_req.return_value = AsyncMock(status_code=200, json=AsyncMock(return_value=[...]))
            df = await client.get("customers")
            assert isinstance(df, pl.DataFrame)
```

**Error Testing:**
```python
def test_select_rejects_empty_field_names(self):
    """Validate that select() rejects empty or whitespace-only field names."""
    with pytest.raises(QueryValidationError, match="Select field cannot be empty"):
        ODataQuery().select("")
```

**Property Testing:**
```python
def test_frozen_dataclass(self):
    """BasicAuth is immutable."""
    auth = BasicAuth("user", "password")
    with pytest.raises(AttributeError):
        auth.username = "new_user"
```

**Mocking Time-Dependent Code:**
```python
def test_cache_expiration(self):
    """Test TTL-based cache expiration."""
    metadata = CacheMetadata(
        url="https://api.example.com/data",
        params=None,
        created_at=0.0,  # Very old (epoch time)
        ttl_seconds=3600,
    )
    assert metadata.is_expired is True  # Created at epoch, definitely expired
```

## Test Execution Modes

**Standard (default):**
```bash
pytest
```
Runs all tests except those marked slow/integration, with verbose output and coverage.

**Development (fast):**
```bash
pytest -m "not slow and not integration"
```
Exclude slow and integration tests for quick feedback.

**Full coverage:**
```bash
pytest --cov=src/odyn --cov-report=html
```
Generate detailed coverage HTML report in `htmlcov/`.

**Specific test file/class:**
```bash
pytest tests/test_client.py
pytest tests/test_client.py::TestBCWebServiceClientCreate
```

## Fixtures Configuration

**Key Settings in pyproject.toml:**
- `testpaths = ["tests"]` - Only discover tests in tests/ directory
- `pythonpath = ["."]` - Add project root to Python path for imports
- `asyncio_mode = "auto"` - Automatic async fixture handling
- `asyncio_default_fixture_loop_scope = "function"` - Fresh event loop per test

**Warning Filters:**
```
filterwarnings = [
    "error",  # Treat warnings as errors
    "ignore::DeprecationWarning",  # Except deprecation warnings
]
```

---

*Testing analysis: 2026-03-22*
