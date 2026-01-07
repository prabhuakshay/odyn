import asyncio

from odyn import BasicAuth, BCWebServiceClient
from odyn.query import F, ODataQuery


async def main():
    async with BCWebServiceClient.create(...) as client:
        # Build complex queries using the fluent DSL
        query = (
            ODataQuery()
            .select("No", "Name", "Balance", "City")
            .filter(F.Status == "Active")
            .filter(F.Balance > 1000)
            .filter(F.Country_Region_Code.is_in(["US", "GB"]))
            .order_by("Balance desc")
            .top(50)
        )

        # Requests: $select=No,Name,Balance,City&$filter=Status eq 'Active' and ...
        df = await client.get("customers", query=query)

        # Expanding related records
        query_expanded = ODataQuery().select("No", "External_Document_No").expand("SalesLines").top(10)
        sales_orders = await client.get("SalesOrders", query=query_expanded)


if __name__ == "__main__":
    asyncio.run(main())
