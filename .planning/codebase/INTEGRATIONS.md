# External Integrations

**Analysis Date:** 2026-03-22

## APIs & External Services

**Microsoft Dynamics 365 Business Central:**
- OData Web Services (on-premises only)
  - SDK/Client: Custom httpx async client in `src/odyn/client.py`
  - Auth: BasicAuth (Base64-encoded credentials) or APIKeyAuth (custom header)
  - Endpoint pattern: `https://{server}:{port}/DynamicsNAV/OData`
  - Query format: OData v2/v3 syntax via `src/odyn/query/` builder
  - Response handling: JSON responses parsed into Polars DataFrames
  - Features: Automatic pagination, retry with exponential backoff, rate limiting

## Data Storage

**Databases:**
- Business Central on-premises (external, read-only via OData)
  - Connection: HTTP/HTTPS via httpx async client
  - Auth: BasicAuth or APIKeyAuth (no direct database connection)
  - Client: Custom async wrapper around httpx (not an ORM)

**File Storage:**
- Local filesystem only via ParquetCache
  - Location: User-specified directory (default None, optional)
  - Format: Parquet (.parquet files) with JSON metadata
  - TTL-based expiration: Per-entry or cache-wide default

**Caching:**
- Local Parquet-based cache (`src/odyn/cache.py`)
  - ParquetCache: File-based, no external service
  - Key generation: SHA256 hash of URL + sorted query params
  - No Redis, Memcached, or cloud storage integration

## Authentication & Identity

**Auth Provider:**
- Custom (BasicAuth or APIKeyAuth)
  - BasicAuth implementation: `src/odyn/auth.py`
    - Format: DOMAIN\username:password (Base64 encoded)
    - Supports Windows domain credentials for on-premises BC
  - APIKeyAuth implementation: `src/odyn/auth.py`
    - Custom header name (default: X-API-Key)
    - Optional prefix (e.g., Bearer, empty by default)
    - Used for modern BC instances or custom authentication

**No external identity providers:** No OAuth2, SAML, Azure AD, or third-party auth services. On-premises only.

## Monitoring & Observability

**Error Tracking:**
- None integrated; application provides rich exception hierarchy in `src/odyn/exceptions.py`:
  - OdynError (base)
  - QueryValidationError
  - AuthenticationError / ForbiddenError
  - ConnectionError / TimeoutError / SSLError
  - NotFoundError / RateLimitError
  - ServerError
  - RetryExhaustedError
  - WebServiceError (generic HTTP errors)

**Logs:**
- Standard Python logging module (`logging`)
  - Logger: `odyn.client`
  - Configurable via `_configure_logging()` utility in `src/odyn/client.py`
  - Request/response hooks available via RequestHook and ResponseHook protocols
  - Default logging level: INFO
  - Example hook usage in `examples/08_configuration.py`

**Request/Response Tracing:**
- Optional hooks (not automatic):
  - RequestHook: Called before each HTTP request (method, URL, params)
  - ResponseHook: Called after each HTTP response (method, URL, status, duration_ms)
  - Implementations are user-provided, not built-in

## CI/CD & Deployment

**Hosting:**
- Not applicable; Odyn is a library, not a service
- Consumed by applications that run on any Python 3.12+ environment

**CI Pipeline:**
- Pre-commit hooks (`.pre-commit-config.yaml`):
  - Ruff check and format
  - Bandit security scanning
  - Trailing whitespace, YAML/TOML/JSON validation
  - Large file detection (>1000 KB warning)
  - Private key detection
  - uv lock and sync validation
  - Commitizen message validation
- No GitHub Actions or external CI service configured (repository-level setup only)
- Test execution: `pytest` with coverage reporting to console and HTML

## Environment Configuration

**Required env vars:**
- None (all configuration passed programmatically)
- Server URL, credentials, company name, rate limits passed to `BCWebServiceClient.create()`

**Optional env vars:**
- None enforced; application-specific (not library responsibility)
- Cache directory path passed as argument, not env var

**Secrets location:**
- Credentials passed in code (not loaded from env)
- BasicAuth credentials: Username + password arguments
- APIKeyAuth: API key argument
- SSL verification: Optional `verify_ssl` parameter (defaults to True)
- No .env file support in Odyn itself; delegated to consuming application

## Webhooks & Callbacks

**Incoming:**
- None; Odyn is a client, not a server

**Outgoing:**
- None to external services
- Optional progress callbacks (user-provided) during pagination:
  - ProgressCallback: Page-level progress reporting
  - BatchProgressCallback: Batch-level progress reporting (if implemented)
- Optional hooks for request/response interception (RequestHook, ResponseHook)

## Special Integration Patterns

**OData Query Building:**
- Fluent builder pattern: `src/odyn/query/builder.py`
- Field filtering: `src/odyn/query/fields.py` with type-safe F singleton
- Expression generation: `src/odyn/query/expressions.py`
- Output: Dict of OData query parameters ($filter, $select, $expand, $top, $skip, $orderby)

**Retry & Rate Limiting:**
- aiolimiter integration: Automatic rate limiting (configurable requests/minute)
- Exponential backoff: Implemented in `src/odyn/client.py`, configurable base delay and max retries
- Transient error handling: 429 (rate limit), 5xx (server errors), connection errors

**Async Streaming:**
- AsyncIterator for large datasets: `get_stream()` method in `src/odyn/client.py`
- Page-by-page processing: Prevents loading entire dataset into memory
- Automatic pagination: Skip/top parameters managed internally

---

*Integration audit: 2026-03-22*
