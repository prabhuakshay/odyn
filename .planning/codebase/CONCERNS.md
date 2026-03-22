# Codebase Concerns

**Analysis Date:** 2026-03-22

## Tech Debt

**Type Annotation Gap in `count()` Method:**
- Issue: The `count()` method at `src/odyn/client.py:1109` calls `_request("GET", ...)` and expects a plain text integer, but the return type annotation suggests JSON dict. The logic assumes the response is a string and converts it with `int()`, but `_request()` tries to parse JSON first via `response.json()`, which will fail for plain text integer responses.
- Files: `src/odyn/client.py` (lines 1109-1112)
- Impact: The `$count` endpoint returns plain text like "42" without JSON wrapping. The current code path will fail or return incorrect results when calling `count()`.
- Fix approach: Implement a specialized request handler for `$count` endpoints that expects plain text responses, or catch JSON parsing errors and fall back to text parsing. Add type narrowing or separate internal method `_request_text()`.

**Synchronous Wrapper Background Event Loop Management:**
- Issue: `src/odyn/sync.py` implements a background event loop for sync operations, but there's no mechanism to ensure the loop is properly cleaned up on unexpected termination.
- Files: `src/odyn/sync.py` (lines 81-106)
- Impact: If the process crashes or exits unexpectedly, the background thread may not shut down cleanly, potentially leaving resources open or hanging processes. The daemon thread will be forcibly terminated.
- Fix approach: Add explicit cleanup in `__del__` or provide a `close()` method. Consider using context managers with guarantees. Add logging for thread lifecycle.

**Limited Error Context in Batch Operations:**
- Issue: `src/odyn/client.py:1437-1444` catches all exceptions during batch processing but logs only `len(batch_values)` and the exception, losing context about which specific values failed.
- Files: `src/odyn/client.py` (lines 1407-1462)
- Impact: Debugging batch failures is difficult. Users cannot determine which items caused a batch to fail, making retry logic problematic.
- Fix approach: Store batch values → results mapping. Return detailed error report with per-item status. Add structured logging with batch ID/index.

**Semaphore and Rate Limiter Interaction:**
- Issue: Semaphore for concurrency control (line 666) is acquired AFTER rate limiting is applied (line 668), but the comment says "inside semaphore to avoid queuing". The rate limiter's token bucket can still create queuing behavior that's not visible to users.
- Files: `src/odyn/client.py` (lines 665-668)
- Impact: Request ordering may be unintuitive. Requests can be delayed by rate limiting independent of concurrency limits, potentially causing long tail latencies.
- Fix approach: Document the interaction clearly. Consider making rate limiting and semaphore behavior more explicit to users. Add metric hooks for observability.

## Known Bugs

**Cache Metadata Deserialization Without Error Handling:**
- Issue: `src/odyn/cache.py:163` calls `json.loads()` without catching `json.JSONDecodeError` if metadata file is corrupted.
- Files: `src/odyn/cache.py` (lines 151-164)
- Impact: Corrupted `.json` metadata files will raise unhandled exceptions and crash the entire cache lookup, making the system unusable even if Parquet files are intact.
- Workaround: Manually delete corrupted `.json` files from cache directory.
- Fix approach: Wrap JSON loading in try/except, return None on decode error (treat as miss), log warnings for corrupted entries.

**Incomplete Type Annotation in `_request()` Exception Handling:**
- Issue: `src/odyn/client.py:766` passes `last_exception` (which may be None) to `RetryExhaustedError` despite type hint `Exception` (not optional).
- Files: `src/odyn/client.py` (lines 661-767)
- Impact: If retry loop exits early without setting `last_exception` (which shouldn't happen but guards against future changes), it will pass None to the exception constructor, causing AttributeError downstream.
- Fix approach: Initialize `last_exception` to a sentinel value or explicitly guard against None. Add assertion that `last_exception is not None` before raising.

**String Field Names in Parquet Cache Key Generation:**
- Issue: `src/odyn/cache.py:399` encodes params dict items as URL query string without explicit sorting guarantees beyond `sorted()` on tuple pairs. Floating-point or special dict iteration order edge cases could theoretically cause cache key collisions.
- Files: `src/odyn/cache.py` (lines 369-400)
- Impact: Cache misses for functionally identical queries if parameter representation differs (extremely rare in practice).
- Fix approach: Use `json.dumps(params, sort_keys=True, separators=(',', ':'))` for deterministic serialization before hashing.

## Security Considerations

**Credentials Stored in Base64 Without Warnings:**
- Risk: Basic authentication credentials are Base64 encoded but stored in `BasicAuth` dataclass. If the client is pickled or serialized, credentials could leak. The `__repr__` hides passwords but doesn't prevent serialization attacks.
- Files: `src/odyn/auth.py` (lines 29-73)
- Current mitigation: `__repr__` masks password display. Credentials only in memory and httpx Authorization header.
- Recommendations: Add `__getstate__` / `__setstate__` to prevent pickling. Document that credentials should never be logged. Consider raising warning if auth objects are printed unintentionally. Use `secrets` module for PRNG if jitter uses insecure random source.

**Random Number Generation for Jitter Not Cryptographically Secure:**
- Risk: `src/odyn/client.py:623` uses `random.uniform()` with `# noqa: S311` comment dismissing bandit security check. For retry backoff jitter, this is acceptable, but the comment suggests developers may use this pattern elsewhere inappropriately.
- Files: `src/odyn/client.py` (line 623)
- Current mitigation: Only used for retry jitter (low security impact). Comment documents the suppression.
- Recommendations: Replace with `secrets.SystemRandom().uniform()` or document explicitly why this usage is safe. Remove the `# noqa` comment and replace with a more specific type-ignore if using standard library random is intentional.

**SSL Verification Can Be Disabled Without Warning:**
- Risk: `verify_ssl=False` parameter allows MITM attacks for self-signed certificates. No warning emitted when SSL verification is disabled.
- Files: `src/odyn/client.py` (lines 340, 295-296)
- Current mitigation: Parameter is documented. Default is `True`.
- Recommendations: Log WARNING when `verify_ssl=False` is set. Document that this should only be used in development. Consider requiring opt-in via environment variable for production.

## Performance Bottlenecks

**DataFrame Concatenation with `diagonal_relaxed` in Pagination:**
- Problem: `src/odyn/client.py:850` and `src/odyn/client.py:1490` use `pl.concat(..., how="diagonal_relaxed")` which may be slower than `how="vertical_relaxed"` or `how="vertical"` for uniform schemas. Schema relaxation mode is used to handle potential schema variations across pages.
- Files: `src/odyn/client.py` (lines 805-852, 1407-1490)
- Cause: Over-cautious schema handling. OData endpoints typically return consistent schemas across pages. Diagonal concatenation requires duplicate column detection.
- Improvement path: Validate first page schema and use strict concatenation for subsequent pages. Add per-endpoint schema caching. Profile to measure if this is actually a bottleneck (likely negligible for typical dataset sizes).

**Semaphore Blocks Rate Limiter Application:**
- Problem: `src/odyn/client.py:666-668` acquires semaphore before rate limiting. If semaphore is full, waiting requests don't apply rate limiting, causing bursty behavior when semaphore releases.
- Files: `src/odyn/client.py` (lines 626-770)
- Cause: Rate limiter is only called inside the semaphore-guarded section.
- Improvement path: Swap the order: apply rate limit outside semaphore, then acquire semaphore. This ensures consistent rate limiting independent of concurrency saturation.

**Cache Hit Check Performs Disk I/O Twice:**
- Problem: `src/odyn/cache.py:292-295` in `exists()` method calls `_load_metadata()` (JSON read) and then `_parquet_path().exists()` (stat call). `get()` at line 207 also calls both. Two filesystem operations per cache check.
- Files: `src/odyn/cache.py` (lines 193-218, 276-295)
- Cause: Defensive programming to handle orphaned files.
- Improvement path: Cache the metadata result to avoid double load. Or use single `glob()` to check both files exist. For typical small cache directories, impact is negligible.

**Large Client File (1554 lines):**
- Problem: `src/odyn/client.py` at 1554 lines is difficult to navigate, modify, and test. High cyclomatic complexity in `_request()` method with retry loop and error handling.
- Files: `src/odyn/client.py` (entire file)
- Cause: Rich functionality bundled into single class. Multiple concerns: HTTP, retries, pagination, batching, caching, hooks.
- Improvement path: Extract pagination logic to `Paginator` class. Extract retry logic to `RetryStrategy` class. Extract batch logic to `BatchFetcher` class. This would improve testability without changing external API.

## Fragile Areas

**Authentication Header Initialization:**
- Files: `src/odyn/client.py` (lines 298-302)
- Why fragile: Headers dict is initialized in `__post_init__` with `auth.auth_header`. If `auth` is changed after initialization, headers won't update. No validation that auth object is actually valid.
- Safe modification: Add post-init validation. Consider making `auth` property with setter that updates headers if needed.
- Test coverage: Tests mock auth but don't test auth state changes.

**Pagination Loop with Max Pages Limit:**
- Files: `src/odyn/client.py` (lines 811-838, 879-898)
- Why fragile: Two parallel pagination implementations (`_paginate` and `_paginate_stream`). If one is updated, the other must be kept in sync. `max_pages` limit silently stops pagination without returning error to user.
- Safe modification: Extract common pagination logic to shared iterator. Test both with large datasets that exceed max_pages.
- Test coverage: Tested but edge case of max_pages boundary is fragile.

**Error Response Parsing with Fallback Chain:**
- Files: `src/odyn/client.py` (lines 475-483, 562-574)
- Why fragile: Tries JSON parsing (line 479), silently catches ValueError/KeyError (line 481), then tries to extract from OData structure (line 480). If OData response format changes, extraction fails silently. Multiple sources of truth for error messages.
- Safe modification: Add explicit schema validation for OData error format. Log warnings when fallback occurs. Add structured error parsing tests with real BC error responses.
- Test coverage: Tested with mock responses but not with real malformed OData responses.

**Batch Value Chunking Without Validation:**
- Files: `src/odyn/client.py` (lines 1366-1380)
- Why fragile: Batch size is divided into chunks with `[values[i : i + batch_size] for i in range(0, len(values), batch_size)]` but no validation that values list is not empty or too large. If `batch_size=0` is passed, infinite loop occurs (though not a user error with defaults).
- Safe modification: Validate `batch_size > 0` and `len(values) > 0` at start. Add guard against empty batches.
- Test coverage: Good coverage but missing edge case of empty values list.

## Scaling Limits

**Rate Limiter Token Bucket Time Period Calculation:**
- Current capacity: Default 550 requests/minute with burst of max_connections (4).
- Limit: The `time_period = 60.0 * burst / requests_per_minute` calculation (line 313) means with burst=4 and rate=550 req/min, time_period≈0.44s. Tokens replenish very frequently, which could cause high CPU usage from timer events.
- Scaling path: For very high sustained rates (>2000 req/min), consider batching token release or using server-side rate limit headers instead.

**Concurrent Request Limit:**
- Current capacity: Default `max_connections=4` controls both httpx connection pooling and semaphore. This is conservative for BC on-premises but aggressive for cloud.
- Limit: Fixed at initialization time. Cannot be adjusted without creating new client. No dynamic scaling based on server response.
- Scaling path: Make `max_connections` adjustable at runtime. Add 429 response handling that temporarily reduces concurrency. Implement connection pool warm-up.

**Pagination Without Cursor or Offset State:**
- Current capacity: Can fetch up to `max_pages=100` pages (default). Each page is typically 500-5000 records.
- Limit: `@odata.nextLink` following works well for small datasets but becomes problematic for multi-million record sets where pagination tokens grow large or stale.
- Scaling path: Add support for `$skip` / `$top` pagination as fallback. Cache `@odata.nextLink` values. Add resumable pagination that saves position and can restart from checkpoint.

**Cache Directory Not Size-Limited:**
- Current capacity: No limit on total cache disk usage.
- Limit: Cache can grow unboundedly. `cleanup()` only removes expired entries, not oldest/largest.
- Scaling path: Add cache size limit (e.g., max_bytes). Implement LRU eviction. Add cache quota warnings when approaching limit.

## Dependencies at Risk

**Polars Version Constraint:**
- Risk: Dependency on `polars>=1.36.1` with no upper bound. Polars is in active development (0.x to 1.x transition). Major API changes are possible.
- Impact: Future Polars versions may change `concat()` parameters, `read_parquet()` format, or DataFrame API.
- Migration plan: Pin to `>=1.36.1,<2.0`. Monitor Polars changelog. Add integration tests with both Polars 1.x and 2.x (once released).

**httpx Dependency Version:**
- Risk: `httpx>=0.28.1` with no upper bound. httpx is actively developed and occasionally breaks API (e.g., auth handler changes).
- Impact: Future httpx versions may change exception types, timeout handling, or async context manager behavior.
- Migration plan: Pin to `>=0.28.1,<1.0`. Test each httpx update before upgrading.

**aiolimiter Dependency:**
- Risk: Small, less-maintained library (`aiolimiter>=1.2.1`). No upper bound specified.
- Impact: If aiolimiter is abandoned, no fixes for Python 3.13+ or asyncio changes. Could be replaced with asyncio.Semaphore but that doesn't offer rate limiting.
- Migration plan: Consider backporting rate limiting logic (token bucket is simple). Monitor package maintenance. Have fallback plan to implement in-house if needed.

## Test Coverage Gaps

**Count Endpoint Not Tested Properly:**
- What's not tested: The actual type handling for `$count` plain text response. Tests likely mock the response as JSON.
- Files: `src/odyn/client.py` (lines 1082-1112), `tests/test_client.py` (lines 483-507)
- Risk: `count()` method may fail or return 0 silently on real BC servers if response handling is incorrect.
- Priority: High - affects core API functionality.

**Authentication Edge Cases:**
- What's not tested:
  - DOMAIN\\user format (mentioned in docstrings)
  - Mixed auth strategy switching (BasicAuth to APIKeyAuth)
  - Auth state corruption
- Files: `src/odyn/auth.py`, `tests/test_auth.py` (95 lines, minimal coverage)
- Risk: Domain authentication might fail or encode incorrectly.
- Priority: Medium - affects on-premises deployments.

**Cache Corruption Scenarios:**
- What's not tested:
  - Corrupted `.json` metadata files (will crash cache.get())
  - Orphaned files (parquet without json or vice versa)
  - Filesystem permission issues
  - Cache file deletion during operation
- Files: `src/odyn/cache.py`, `tests/test_cache.py` (1098 lines, good coverage but missing edge cases)
- Risk: Real-world cache corruption will cause crashes instead of graceful fallback.
- Priority: Medium - affects reliability in production.

**SSL/TLS Error Handling:**
- What's not tested:
  - Real SSL certificate errors (tests mock)
  - Self-signed certificate handling with `verify_ssl=False`
  - Certificate chain validation
  - SNI (Server Name Indication) issues
- Files: `src/odyn/client.py` (lines 726-732), `tests/test_resilience.py` (no SSL tests)
- Risk: SSL errors may not be caught correctly or reported clearly.
- Priority: Medium - affects secure deployments.

**Batch Operation Large Scale:**
- What's not tested:
  - Batches with thousands of values (memory, performance)
  - Partial batch failures (fail_fast=False)
  - Mixed success/failure results
  - Progress callback correctness under concurrent load
- Files: `src/odyn/client.py` (lines 1314-1490), `tests/test_client.py` (batch tests exist but limited)
- Risk: Batch operations may hang or leak memory with very large value lists.
- Priority: Low - affects advanced usage.

**Sync Wrapper Thread Safety:**
- What's not tested:
  - Multiple threads calling sync client simultaneously
  - Cleanup/shutdown race conditions
  - Event loop cleanup under exceptions
- Files: `src/odyn/sync.py`, `tests/test_sync.py` (331 lines)
- Risk: Concurrent sync access may cause event loop errors or hanging.
- Priority: Medium - could affect multi-threaded applications.

---

*Concerns audit: 2026-03-22*
