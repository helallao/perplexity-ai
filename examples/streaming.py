"""
Streaming response example.

This example demonstrates how to use streaming to receive
responses in real-time as they are generated.
"""

import perplexity


def main():
    """Run streaming example."""
    print("=" * 60)
    print("Perplexity API - Streaming Example")
    print("=" * 60)

    # Create client
    print("\n[1/2] Creating client...")
    client = perplexity.Client()

    # Stream response
    print("\n[2/2] Streaming response...")
    query = "Explain quantum computing in simple terms"
    print(f"\nQuery: {query}")
    print("\nStreaming response:")
    print("-" * 60)

    chunk_count = 0
    last_answer = None

    for chunk in client.search(query, mode="auto", stream=True):
        chunk_count += 1

        # Print progress indicator
        if chunk_count % 10 == 0:
            print(f"[Received {chunk_count} chunks...]")

        # Store last chunk with answer
        if "answer" in chunk:
            last_answer = chunk["answer"]

    print(f"\nTotal chunks received: {chunk_count}")

    if last_answer:
        print("\nFinal answer:")
        print("-" * 60)
        print(last_answer)
        print("-" * 60)

    print("\n" + "=" * 60)
    print("Streaming example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
