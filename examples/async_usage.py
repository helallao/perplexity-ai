"""
Async usage example.

This example demonstrates how to use the async API
for non-blocking operations and concurrent queries.
"""

import asyncio
import perplexity_async

async def single_query():
    """Make a single async query."""
    print("\n[Example 1] Single async query")
    print("-" * 60)
    
    client = await perplexity_async.Client()
    response = await client.search("What is machine learning?")
    
    if 'answer' in response:
        print(response['answer'][:200] + "...")


async def multiple_queries():
    """Make multiple concurrent queries."""
    print("\n[Example 2] Multiple concurrent queries")
    print("-" * 60)
    
    client = await perplexity_async.Client()
    
    queries = [
        "What is AI?",
        "What is ML?",
        "What is deep learning?"
    ]
    
    # Execute concurrently
    tasks = [client.search(q) for q in queries]
    responses = await asyncio.gather(*tasks)
    
    for query, response in zip(queries, responses):
        print(f"\nQ: {query}")
        if 'answer' in response:
            print(f"A: {response['answer'][:100]}...")


async def streaming_async():
    """Stream response asynchronously."""
    print("\n[Example 3] Async streaming")
    print("-" * 60)
    
    client = await perplexity_async.Client()
    response_gen = await client.search(
        "Explain neural networks",
        stream=True
    )
    
    chunk_count = 0
    async for chunk in response_gen:
        chunk_count += 1
        if 'answer' in chunk:
            print(f"\nReceived answer in chunk {chunk_count}")
            print(chunk['answer'][:150] + "...")
            break


async def main():
    """Run all async examples."""
    print("=" * 60)
    print("Perplexity API - Async Examples")
    print("=" * 60)
    
    await single_query()
    await multiple_queries()
    await streaming_async()
    
    print("\n" + "=" * 60)
    print("Async examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
