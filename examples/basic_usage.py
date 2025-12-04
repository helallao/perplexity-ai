"""
Basic usage example of Perplexity API.

This example demonstrates the simplest way to use the library
for making queries without account management.
"""

import perplexity


def main():
    """Run basic example."""
    print("=" * 60)
    print("Perplexity API - Basic Usage Example")
    print("=" * 60)

    # Create client (no authentication needed for basic queries)
    print("\n[1/3] Creating client...")
    client = perplexity.Client()
    print(f"Client created. Available queries: {client.copilot}")

    # Simple query
    print("\n[2/3] Making query...")
    query = "What is artificial intelligence?"
    response = client.search(query, mode="auto")

    print("\nQuery:", query)
    print("\nResponse:")
    print("-" * 60)
    if "answer" in response:
        print(response["answer"])
    else:
        print("No answer field found in response")
    print("-" * 60)

    # Query with different sources
    print("\n[3/3] Query with specific sources...")
    query = "Latest AI research 2024"
    response = client.search(query, mode="auto", sources=["scholar"])  # Academic papers only

    print("\nQuery:", query)
    print("Sources: Academic papers")
    print("\nResponse:")
    print("-" * 60)
    if "answer" in response:
        print(response["answer"][:300] + "...")
    print("-" * 60)

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
