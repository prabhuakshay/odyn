# Odyn Documentation

Odyn is an async-first Python client for Microsoft Dynamics 365 Business Central on-premises OData Web Services. It returns Polars DataFrames with built-in caching, rate limiting, retry logic, and a fluent query builder.

## Guides

| Guide | What it covers |
|-------|---------------|
| [Getting Started](getting-started.md) | Installation, prerequisites, your first query |
| [Client](client.md) | Creating and configuring `BCWebServiceClient` |
| [Authentication](auth.md) | `BasicAuth`, `APIKeyAuth`, custom headers |
| [Query Builder](query.md) | `ODataQuery`, the `F` singleton, filters, expressions |
| [Caching](cache.md) | `ParquetCache`, TTL, cache keys, management |
| [Sync Client](sync.md) | `BCWebServiceClientSync` for non-async contexts |
| [Advanced](advanced.md) | Hooks, streaming, batch operations, delta sync, concurrency tuning |
| [Exceptions](exceptions.md) | Exception hierarchy and error handling patterns |
| [Troubleshooting](troubleshooting.md) | Common issues with BC on-premises and OData |

## Reference

| Reference | What it covers |
|-----------|---------------|
| [API Reference](api.md) | Every public class, method, parameter, and type |
| [LLM Context](llm-context.md) | Single-file complete reference for AI assistants |

## Design Principles

1. **Async-first.** All network I/O is async via httpx. A sync wrapper runs async ops in a background thread for scripts, notebooks, and frameworks that don't support async.

2. **Polars DataFrames.** All multi-record responses are Polars DataFrames — columnar, fast, memory-efficient.

3. **Resilience by default.** Exponential backoff with jitter, token-bucket rate limiting, concurrency semaphores, and automatic pagination are all on by default with sensible defaults for BC on-premises.

4. **Type-safe query builder.** The `F` singleton and expression DSL catch filter errors at construction time, not at HTTP time.

5. **OData Web Services only.** Odyn targets the `/ODataV4` endpoint exposed by BC on-premises Web Services. It does not cover the standard BC API v2.0 REST endpoints.
