# Changelog

## [0.5.1] - 2026-03-23

### Fixed
- `APIKeyAuth` now sends the key in the correct header (e.g. `X-API-Key`) instead of always using `Authorization`

## [0.5.0] - 2026-03-22

### Added
- `APIKeyAuth` class for API key-based authentication with configurable header name and prefix
- `AuthStrategy` type alias (`BasicAuth | APIKeyAuth`)

### Changed
- `APIKeyAuth` defaults to `X-API-Key` header with no prefix (instead of `Authorization: Bearer`)
- Rewrote all documentation: README, API reference, and all guides
- Added new doc pages: Getting Started, Sync Client, Advanced Usage

## [0.4.2] - 2026-02-27

- Fixed cache ignoring current `default_ttl` on reads — entries written without a TTL (or by a previous session) now correctly expire based on the cache's current `default_ttl`

## [0.4.1] - 2026-02-14

- Fixed duplicate log handlers when client is initialized multiple times

## [0.4.0] - 2026-01-16

- **BREAKING**: Renamed `rate_limit` to `requests_per_minute` for clarity
- Added `max_burst` parameter to control burst size (defaults to `max_connections`)
- Moved rate limit check inside semaphore to avoid queuing waiting requests
- Added cache statistics: `ParquetCache.stats()` returns hits, misses, disk_bytes
- Added `cache_stats` property on client for easy access
- Added progress callbacks: `ProgressCallback` for pagination, `BatchProgressCallback` for batches
- Added `on_progress` parameter to `get()`, `get_stream()`, `get_batch()`
- Added request/response hooks: `RequestHook` and `ResponseHook` protocols
- Added `on_request`, `on_response` parameters to `create()`
- Added delta sync helpers: `get_since(timestamp)` and `get_before(timestamp)`
- Added `BCWebServiceClientSync`: Synchronous wrapper for non-async contexts

## [0.3.0] - 2026-01-09

- Replaced custom rate limiting with `aiolimiter` (token bucket algorithm)
- Rate limit now specified in requests per minute instead of per second
- Default rate limit: 550 req/min (~9.17 req/s)
- Default max concurrent connections changed from 5 to 4
- Added `aiolimiter>=1.2.1` dependency

## [0.2.0] - 2026-01-09

Initial release. Async-first Python client for Business Central OData Web Services.

- `BCWebServiceClient`: Async HTTP client with automatic pagination, caching, streaming
- Resilience: Exponential backoff retries, rate limiting, concurrency control
- Methods: `get()`, `get_stream()`, `get_by_key()`, `get_by_id()`, `count()`, `exists()`, `get_all()`, `get_batch()`
- `ODataQuery`: Fluent builder for `$select`, `$filter`, `$expand`, `$orderby`, `$top`, `$skip`
- `F` proxy for type-safe field expressions (e.g., `F.Balance > 1000`)
- Logical operators (`&`, `|`) and `is_in()` for complex filters
- `ParquetCache`: Local DataFrame caching with TTL and SHA256 keys
- `BasicAuth`: On-premises authentication with `DOMAIN\user` support
- Structured exception hierarchy: `OdynError`, `WebServiceError`, `RetryExhaustedError`, etc.
