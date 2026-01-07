import asyncio

from odyn import BasicAuth, BCWebServiceClient


async def main():
    async with BCWebServiceClient.create(...) as client:
        # 1. Fetch by Primary Key
        customer = await client.get_by_key("customers", "C00010")
        if customer:
            print(f"Found: {customer['Name']}")

        # 2. Fetch by SystemId (GUID)
        record = await client.get_by_id("customers", "00000000-0000-0000-0000-000000000000")

        # 3. Check for existence without downloading full record
        if await client.exists("vendors", "V12345"):
            print("Vendor exists")

        # 4. Get the first record matching a condition
        from odyn.query import F, ODataQuery

        first_gold_cust = await client.get_first(
            "customers", query=ODataQuery().filter(F.Customer_Posting_Group == "GOLD")
        )


if __name__ == "__main__":
    asyncio.run(main())
