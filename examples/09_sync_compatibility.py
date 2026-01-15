from odyn import BasicAuth, BCWebServiceClientSync

# For non-async contexts (scripts, notebooks, Django views),
# use BCWebServiceClientSync. It provides blocking versions
# of all async methods.


def main():
    # The sync client works as a context manager
    with BCWebServiceClientSync.create(
        server="https://bc-server:7048",
        instance="BC240",
        auth=BasicAuth("user", "pass"),
    ) as client:
        # All methods are blocking (no await needed)
        customers = client.get("customers")
        print(f"Found {len(customers)} customers")

        # Single record lookups
        customer = client.get_by_key("customers", "10000")
        print(f"Customer: {customer['Name']}")

        # Check existence
        exists = client.exists("customers", "10000")
        print(f"Customer 10000 exists: {exists}")

        # Get record count
        count = client.count("customers")
        print(f"Total customers: {count}")


if __name__ == "__main__":
    main()
