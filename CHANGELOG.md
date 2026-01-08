# Changelog

All notable changes to Odyn will be documented in this file.

## [0.2.0] - 2026-01-09

Initial release of Odyn: A modern, async-first Python client for Business Central OData Web Services.
Skipping `0.1.0` since another package with that package existed and since has been deleted.

### Added

- `odyn.client` module for async Business Central Web Services access:
  - `BCWebServiceClient` - Async HTTP client with automatic pagination, caching, and streaming.
  - Resilience features: Exponential backoff retries, rate limiting, and concurrency control.
  - Comprehensive API: `get()`, `get_stream()`, `get_by_key()`, `get_by_id()`, `count()`, `exists()`, `get_all()`.

- `odyn.query` module for fluent OData query building:
  - `ODataQuery` builder with support for `$select`, `$filter`, `$expand`, `$orderby`, `$top`, and `$skip`.
  - Type-safe field expressions using the `F` proxy (e.g., `F.Balance > 1000`).
  - Support for logical operators (`&`, `|`) and `is_in()` expansion for large filters.

- `odyn.cache` module for high-performance data persistence:
  - `ParquetCache` stores Polars DataFrames locally as Parquet files with JSON metadata.
  - Configurable TTL (Time-to-Live) and automatic cache cleanup.

- `odyn.auth` module:
  - `BasicAuth` support specifically optimized for Business Central on-premises (handling `DOMAIN\user` formats).

- `odyn.exceptions` module:
  - Structured exception hierarchy for network, authentication, OData, and rate-limiting errors.

- Documentation & Examples:
  - Comprehensive guides in `docs/` covering all core modules.
  - A suite of 10 functional examples in `examples/` demonstrating production-ready patterns.
