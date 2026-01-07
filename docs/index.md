# Odyn Documentation

Odyn is a modern, async-first Python client for Microsoft Dynamics 365 Business Central Web Services (OData). It is designed to be opinionated, high-performance, and developer-friendly, specifically targeting data extraction and integration use cases.

## Getting Started

- [Quick Start](../README.md#quick-example) - Get up and running in minutes.
- [Installation](../README.md#installation) - Add Odyn to your project.

## Core Modules

- [Client](client.md) - Using the `BCWebServiceClient` to interact with Business Central.
- [Query Builder](query.md) - Building type-safe OData queries with `ODataQuery` and `F`.
- [Authentication](auth.md) - Configuring `BasicAuth` for on-premises deployments.
- [Caching](cache.md) - Using the Parquet-based caching system to improve performance.
- [Exceptions](exceptions.md) - Handling errors and understanding the exception hierarchy.
- [Troubleshooting](troubleshooting.md) - Solutions for common connection and OData issues.

## Reference

- [API Reference](api.md) - Detailed documentation for every public class and method.

## Examples

For runnable scripts and advanced patterns, see the [examples/](../examples/) directory in the repository.

## Design Philosophy

Odyn was built with a few core principles:
1. **Async-First**: All network operations are asynchronous, leveraging `httpx`.
2. **Polars Integration**: Data is returned as Polars DataFrames for efficient processing.
3. **Resilience**: Industry-standard retry and rate-limiting patterns are built-in.
4. **Developer Experience**: A fluent, type-safe API reduces boilerplate and errors.
