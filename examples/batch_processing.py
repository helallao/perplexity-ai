"""
Batch processing example.

This example demonstrates how to process multiple queries
efficiently using async batch processing.
"""

import asyncio
import perplexity_async
from time import time

async def process_queries_sequential(queries):
    """Process queries sequentially."""
    print("\n[Method 1] Sequential processing")
    print("-" * 60)
    
    client = await perplexity_async.Client()
    start = time()
    results = []
    
    for i, query in enumerate(queries, 1):
        print(f"Processing query {i}/{len(queries)}...")
        response = await client.search(query)
        results.append(response)
    
    elapsed = time() - start
    print(f"Completed in {elapsed:.2f}s")
    return results


async def process_queries_concurrent(queries):
    """Process queries concurrently."""
    print("\n[Method 2] Concurrent processing")
    print("-" * 60)
    
    client = await perplexity_async.Client()
    start = time()
    
    # Create tasks for all queries
    tasks = [client.search(q) for q in queries]
    
    # Execute concurrently
    print(f"Processing {len(queries)} queries concurrently...")
    results = await asyncio.gather(*tasks)
    
    elapsed = time() - start
    print(f"Completed in {elapsed:.2f}s")
    return results


async def main():
    """Run batch processing example."""
    print("=" * 60)
    print("Perplexity API - Batch Processing Example")
    print("=" * 60)
    
    # Sample queries
    queries = [
        "What is Python?",
        "What is JavaScript?",
        "What is Rust?",
        "What is Go?",
        "What is TypeScript?",
    ]
    
    print(f"\nProcessing {len(queries)} queries...")
    
    # Sequential
    results_seq = await process_queries_sequential(queries)
    
    # Concurrent
    results_con = await process_queries_concurrent(queries)
    
    # Compare results
    print("\n" + "=" * 60)
    print("Results comparison:")
    print("-" * 60)
    
    for i, query in enumerate(queries):
        print(f"\nQuery {i+1}: {query}")
        if 'answer' in results_con[i]:
            print(f"Answer: {results_con[i]['answer'][:80]}...")
    
    print("\n" + "=" * 60)
    print("Batch processing example completed!")
    print("Note: Concurrent processing is typically 3-5x faster")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
