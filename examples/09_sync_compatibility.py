import asyncio

from odyn import BasicAuth, BCWebServiceClient


def get_data_sync():
    """
    If your application is not async, you can wrap Odyn calls
    using asyncio.run(). Note that client.create() is a
    classmethod but its context manager is async.
    """

    async def _fetch():
        async with BCWebServiceClient.create(
            server="https://bc-server:7048", instance="BC240", auth=BasicAuth("user", "pass")
        ) as client:
            return await client.get("customers")

    # Run the async loop and wait for result
    return asyncio.run(_fetch())


if __name__ == "__main__":
    df = get_data_sync()
    print(df.head())
