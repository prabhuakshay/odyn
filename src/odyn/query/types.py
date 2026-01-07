"""This module provides type aliases and constants for OData query expressions."""

from datetime import date, datetime
from typing import Final

__all__ = ["VALID_OPERATORS", "ODataValue"]

# Type alias for odata values
type ODataValue = str | int | float | bool | None | date | datetime

# Valid operators for odata queries
VALID_OPERATORS: Final[frozenset[str]] = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})
