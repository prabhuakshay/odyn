import asyncio

from odyn import AuthenticationError, BasicAuth, BCWebServiceClient, NotFoundError, OdynError, RateLimitError


async def main():
    async with BCWebServiceClient.create(...) as client:
        try:
            # Dangerous operation
            await client.get("invalid_endpoint")

        except NotFoundError:
            print("The OData entity does not exist.")

        except RateLimitError:
            print("Too many requests. Odyn handles retries automatically,")
            print("but this is raised if retries are exhausted.")

        except AuthenticationError:
            print("Invalid credentials or DOMAIN\\user format.")

        except OdynError as e:
            print(f"Base exception for all Odyn-specific errors: {e}")


if __name__ == "__main__":
    asyncio.run(main())
