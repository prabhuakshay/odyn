# Technology Stack

**Analysis Date:** 2026-03-22

## Languages

**Primary:**
- Python 3.12+ - Full codebase, enforced in `pyproject.toml` with `requires-python = ">=3.12"`

## Runtime

**Environment:**
- Python 3.12+ (async-first, uses asyncio)

**Package Manager:**
- uv (fast Python package manager and builder)
- Lockfile: `uv.lock` present, pinned versions enforced

## Frameworks

**Core:**
- httpx 0.28.1+ - Async HTTP client for Business Central OData requests
- Polars 1.36.1+ - DataFrames for efficient columnar data handling
- aiolimiter 1.2.1+ - Rate limiting and request throttling via AsyncLimiter

**Build/Dev:**
- uv_build 0.9.18-0.9.x - Package builder (configured in `pyproject.toml`)
- pytest 9.0.2+ - Test runner
- pytest-asyncio 1.3.0+ - Async test support (auto mode enabled)
- pytest-cov 7.0.0+ - Coverage reporting
- Ruff 0.14.10+ - Linting and formatting
- pyrefly 0.47.0+ - Type checking
- pre-commit 4.5.1+ - Git hooks management
- commitizen 4.11.1+ - Conventional commit enforcement

**Security & Quality:**
- Bandit 1.9.2+ - Security issue detection (pre-commit hook)

## Key Dependencies

**Critical:**
- httpx 0.28.1+ - Handles all HTTP communication with Business Central servers, SSL verification, automatic retry integration
- aiolimiter 1.2.1+ - Manages rate limiting (default 550 requests/minute) and burst control
- Polars 1.36.1+ - Converts OData responses to DataFrames; enables columnar processing and Parquet caching

**Infrastructure:**
- certifi 2026.1.4 - Certificate bundle for SSL verification (transitive via httpx)
- anyio 4.12.1+ - Async compatibility layer for httpx (transitive)
- typing-extensions - Backward compatibility for type hints (conditional on Python <3.13)

## Configuration

**Environment:**
- No required .env file; configuration passed to `BCWebServiceClient.create()` factory
- Optional cache directory (defaults to None, cache disabled unless provided)
- Optional custom logging via `_configure_logging()` utility

**Build:**
- `pyproject.toml` - Single source of truth for dependencies, dev groups, tool config
- Tool configuration:
  - `[tool.ruff]` - Line length 120, Google docstring convention, extensive lint rules
  - `[tool.pytest.ini_options]` - Async support, coverage settings, markers
  - `[tool.pyrefly]` - Type checking configuration, Python 3.12 target
  - `[tool.bandit]` - Security scanning configuration
  - `[tool.commitizen]` - Conventional commit scheme

## Platform Requirements

**Development:**
- Python 3.12+
- uv (for dependency/build management)
- Git (for pre-commit hooks)

**Production:**
- Python 3.12+ runtime
- Network access to Business Central on-premises server (HTTP/HTTPS)
- Optional: disk space for Parquet cache files (ParquetCache uses local filesystem)

**Deployment:**
- No specific deployment platform required; pure Python package
- Can be distributed via PyPI or as wheel/sdist
- Async runtime (asyncio) must be available in host environment

---

*Stack analysis: 2026-03-22*
