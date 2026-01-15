# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Odyn is an async-first Python client for Microsoft Dynamics 365 Business Central on-premises OData Web Services. It provides a fluent API for extracting data from Business Central, returning native Polars DataFrames with built-in caching, rate limiting, and retry logic.

**Key constraints:** This library targets Business Central OData Web Services only (not the standard Business Central API v2.0 endpoints).

## Development Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run all tests with coverage
pytest

# Run a single test file
pytest tests/test_client.py

# Run a specific test
pytest tests/test_client.py::TestBCWebServiceClientCreate::test_create_constructs_correct_base_url

# Run tests excluding slow/integration tests
pytest -m "not slow and not integration"

# Lint and format
ruff check src tests
ruff format src tests

# Type checking (uses pyrefly)
pyrefly check src
```

## Architecture

### Core Components

- **`src/odyn/client.py`** - `BCWebServiceClient`: Main async client using httpx. Handles HTTP requests, automatic pagination, caching integration, retry with exponential backoff, and rate limiting via aiolimiter. Use `BCWebServiceClient.create()` factory method for instantiation.

- **`src/odyn/query/`** - OData query builder module:
  - `builder.py` - `ODataQuery`: Fluent query builder with method chaining (`.select()`, `.filter()`, `.expand()`, `.order_by()`, `.top()`, `.skip()`)
  - `fields.py` - `F` singleton and `Field` class for building type-safe filter expressions (e.g., `F.Balance > 1000`)
  - `expressions.py` - Filter expression classes (`Comparison`, `InList`, `And`, `Or`, `Raw`) that generate OData filter syntax

- **`src/odyn/cache.py`** - `ParquetCache`: File-based DataFrame cache using Parquet format with TTL-based expiration and SHA256 cache keys

- **`src/odyn/auth.py`** - `BasicAuth`: HTTP Basic authentication for on-premises BC (supports DOMAIN\\user format)

- **`src/odyn/exceptions.py`** - Exception hierarchy rooted at `OdynError`:
  - `QueryValidationError` - Invalid OData query construction
  - `ConnectionError/TimeoutError/SSLError` - Network issues
  - `WebServiceError` and subclasses - API errors (401, 403, 404, 429, 5xx)
  - `RetryExhaustedError` - All retry attempts failed

### Query Builder Pattern

```python
from odyn.query import ODataQuery, F

query = (
    ODataQuery()
    .select("No", "Name", "Balance")
    .filter(F.Status == "Active")
    .filter(F.Balance > 1000)        # Multiple filters are AND'd
    .filter(F.Type.is_in(["A", "B"])) # IN list support
    .expand("SalesLines")
    .order_by("Name asc")
    .top(100)
)
params = query.build()  # Returns dict of OData query params
```

### Client Usage Pattern

```python
async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "pass"),
    company="CRONUS",
    requests_per_minute=550.0,  # default, can be None to disable
    max_burst=4,  # defaults to max_connections, prevents server hammering
) as client:
    df = await client.get("customers", query=query)
    record = await client.get_by_key("customers", "C001")
    async for page in client.get_stream("largeDataset"):
        process(page)
```

## Code Style

- Uses Ruff for linting and formatting (line length 120, Google docstring convention)
- Type hints required for all public APIs (enforced by ruff ANN rules)
- Tests use pytest-asyncio with `asyncio_mode = "auto"`
- Dataclasses with `frozen=True, slots=True` for immutable value objects
