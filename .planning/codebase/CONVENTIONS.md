# Coding Conventions

**Analysis Date:** 2026-03-22

## Naming Patterns

**Files:**
- Lowercase with underscores: `client.py`, `query_builder.py`, `cache.py`
- Test files: `test_*.py` or `*_test.py` (using `test_` prefix)
- Package directories: lowercase with underscores (e.g., `odyn/query/`)

**Functions/Methods:**
- Snake_case for all functions and methods
- Private methods/functions: prefixed with underscore `_validate_field_name()`, `_build_url()`
- Factory methods: `create()` pattern used for constructors (e.g., `BCWebServiceClient.create()`)
- Comparison methods in classes: dunder methods with type overrides (e.g., `__eq__`, `__ne__`, `__gt__`)

**Variables:**
- Snake_case for local variables, attributes, parameters
- Private attributes: prefixed with underscore `_select`, `_filters`, `_expand`
- Constants: UPPERCASE (e.g., `VALID_OPERATORS`, `Final[_FieldFactory]`)

**Types/Classes:**
- PascalCase for all class names: `BCWebServiceClient`, `ODataQuery`, `ParquetCache`, `BasicAuth`, `Field`
- Exception classes: PascalCase ending with `Error` or `Exception`
- Protocol classes: PascalCase (e.g., `ProgressCallback`, `RequestHook`, `FilterExpression`)
- Factory/singleton classes: underscore prefix for internal (e.g., `_FieldFactory`, `_FieldAdapter`)

## Code Style

**Formatting:**
- Tool: Ruff (integrated with pyproject.toml)
- Line length: 120 characters
- Quote style: Double quotes for strings (`"double"`)
- Indent style: 4 spaces
- Docstring code formatting: Enabled (docstring_code_format = true)

**Linting:**
- Tool: Ruff with extensive rule set (pyproject.toml `[tool.ruff.lint]`)
- Target Python: 3.12+
- Key enabled rules:
  - Pyflakes (F) - Basic error detection
  - pycodestyle (E, W) - PEP 8 compliance
  - isort (I) - Import sorting
  - PEP8-naming (N) - Naming conventions
  - pyupgrade (UP) - Modern Python syntax
  - flake8-annotations (ANN) - Type hint enforcement on public APIs
  - pydocstyle (D) - Docstring conventions (Google style)
  - flake8-bugbear (B) - Common bugs and design issues
  - flake8-simplify (SIM) - Code simplification
  - perflint (PERF) - Performance anti-patterns

**Relaxed Rules (per-file ignores):**
- Tests (`tests/**/*.py`): Type hints optional (ANN), docstrings optional (D), assertions allowed (S101), private access allowed (SLF001), magic values allowed (PLR2004)
- Examples: Print allowed (T201), unused variables OK (F841), hardcoded passwords OK (S105)
- `__init__.py`: Unused imports allowed (F401)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first in source files)
2. Standard library imports
3. Third-party imports (httpx, polars, aiolimiter, pytest, etc.)
4. Local imports from odyn package
5. TYPE_CHECKING imports (conditional type hints)

**Path Aliases:**
- First-party: `odyn` is configured as a known first-party package in isort config
- Imports use relative paths from package root: `from odyn.client import ...`, `from odyn.query import ...`
- TYPE_CHECKING block usage for avoiding circular imports and lazy imports

**Example Import Pattern:**
```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Self

import httpx
import polars as pl
from aiolimiter import AsyncLimiter

from odyn.cache import ParquetCache
from odyn.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from odyn.auth import AuthStrategy
```

## Error Handling

**Patterns:**
- Custom exception hierarchy rooted at `OdynError` in `src/odyn/exceptions.py`
- Specific exception types for different error scenarios:
  - `QueryValidationError` - Query construction errors
  - `AuthenticationError` - 401 responses
  - `ValidationError` - 400 bad request responses
  - `NotFoundError` - 404 responses
  - `ForbiddenError` - 403 responses
  - `RateLimitError` - 429 responses
  - `ServerError` - 5xx responses
  - `ConnectionError`, `TimeoutError`, `SSLError` - Network issues
  - `RetryExhaustedError` - All retry attempts failed

**Custom Exception Pattern:**
```python
class OdynError(Exception):
    """Base exception for all Odyn errors."""

class ValidationError(OdynError):
    """Raised for 400 bad request responses."""
```

**Raising with Context:**
- Include relevant information in error messages
- Use keyword arguments for structured context in custom exceptions
- Example: `ConnectionError(message, url=url, original_error=original_ex)`

## Logging

**Framework:** Standard Python `logging` module (see imports in `client.py`)

**Patterns:**
- Get logger with `logging.getLogger(__name__)`
- Structured logging with context kwargs (no f-string interpolation in log calls)
- Debug logs for tracing flow, info for milestones, warning for recoverable issues, error for failures

## Comments

**When to Comment:**
- Explain *why*, not *what* (code shows what)
- Non-obvious algorithmic decisions
- Workarounds for external constraints
- Complex business logic or OData-specific quirks

**JSDoc/TSDoc:**
- Google-style docstrings required (enforced by pydocstyle rule D)
- All public APIs must have docstrings
- Args/Returns/Raises sections mandatory
- Example blocks in docstrings for clarity

**Example Google Docstring:**
```python
def get(self, endpoint: str, *, query: ODataQuery | None = None) -> pl.DataFrame:
    """Fetch data from a Business Central OData endpoint.

    Args:
        endpoint: The OData endpoint name (e.g., 'customers', 'invoices').
        query: Optional ODataQuery for filtering, selecting fields, etc.

    Returns:
        A Polars DataFrame containing the queried data.

    Raises:
        ValidationError: If endpoint is empty.
        AuthenticationError: If credentials are invalid.
        NotFoundError: If the endpoint does not exist.

    Example:
        >>> query = ODataQuery().filter(F.Active == True).top(10)
        >>> df = await client.get("customers", query=query)
    """
```

## Function Design

**Size:**
- Keep functions focused and reasonably sized (pylint max_statements = 60)
- Complex business logic factored into private helpers

**Parameters:**
- Use descriptive names
- Keyword-only args for optional parameters (use `*` separator)
- Type hints required for all public APIs (ANN enforcement)
- Maximum 8 arguments per function (per ruff pylint config: max_args = 8)

**Return Values:**
- Explicit return statements preferred over implicit None
- Type hints on all returns
- Return Self for builder methods (method chaining): `def select(self, *fields: str) -> Self:`

**Example:**
```python
def filter(self, condition: FilterExpression) -> Self:
    """Add a filter condition.

    Args:
        condition: A FilterExpression instance.

    Returns:
        Self for method chaining.

    Raises:
        TypeError: If condition is not a FilterExpression.
    """
    if not isinstance(condition, FilterExpression):
        raise TypeError(...)
    self._filters.append(condition)
    return self
```

## Module Design

**Exports:**
- All public APIs listed in `__all__` at module top level
- Example: `__all__ = ["BCWebServiceClient", "ProgressCallback", "RequestHook"]`

**Barrel Files:**
- `src/odyn/query/__init__.py` re-exports main query builders and field factory
- `src/odyn/__init__.py` re-exports top-level client and auth classes

**Dataclasses:**
- Used extensively for immutable value objects
- Frozen and slots enabled: `@dataclass(frozen=True, slots=True)`
- Example: `BasicAuth`, `APIKeyAuth`, `CacheMetadata`, `Field`

**Protocols:**
- Used for dependency injection and structural typing
- Runtime checkable: `@runtime_checkable` decorator
- Examples: `ProgressCallback`, `RequestHook`, `FilterExpression`

---

*Convention analysis: 2026-03-22*
