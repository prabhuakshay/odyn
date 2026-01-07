import asyncio

from odyn import BasicAuth, BCWebServiceClient


async def main():
    async with BCWebServiceClient.create(...) as client:
        # Discover available endpoints on the server
        endpoints = await client.get_endpoints()

        print("Available OData Endpoints:")
        for name in sorted(endpoints):
            print(f" - {name}")

        # You can also use count() to see record volumes
        count = await client.count("customers")
        print(f"Total customers: {count}")


if __name__ == "__main__":
    asyncio.run(main())
