"""OData query builder module.

Example:
    from odyn.query import ODataQuery, F

    query = (
        ODataQuery()
        .filter(F.Status == "Active")
        .filter(F.Balance > 1000)
        .filter(F.Type.is_in(["Sale", "Purchase"]))
    )
    params = query.build()
"""

from odyn.query.builder import ODataQuery
from odyn.query.fields import F, Field

__all__ = [
    "F",
    "Field",
    "ODataQuery",
]
