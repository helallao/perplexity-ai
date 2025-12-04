"""
File upload example.

This example demonstrates how to upload files with queries
for document analysis and Q&A.
"""

import perplexity
from pathlib import Path


def main():
    """Run file upload example."""
    print("=" * 60)
    print("Perplexity API - File Upload Example")
    print("=" * 60)

    # Note: File uploads require an account with cookies
    # This example shows the API structure

    print("\nNote: This example requires Perplexity account cookies")
    print("See README for instructions on obtaining cookies\n")

    # Example with cookies (replace with actual cookies)
    cookies = {
        # 'next-auth.csrf-token': 'your-token',
        # 'next-auth.session-token': 'your-session-token',
    }

    if not cookies or not any(cookies.values()):
        print("No cookies provided. Showing example code only.\n")
        print("Example code:")
        print("-" * 60)
        print(
            """
# With actual cookies:
client = perplexity.Client(cookies)

# Upload a text file
with open('document.txt', 'r') as f:
    response = client.search(
        'Summarize this document',
        files={'document.txt': f.read()}
    )

# Upload a PDF (as bytes)
with open('report.pdf', 'rb') as f:
    response = client.search(
        'What are the key findings in this report?',
        files={'report.pdf': f.read()}
    )

# Multiple files
files = {
    'doc1.txt': open('doc1.txt').read(),
    'doc2.txt': open('doc2.txt').read(),
}
response = client.search(
    'Compare these two documents',
    files=files
)
        """
        )
        print("-" * 60)
        return

    # Actual implementation with cookies
    client = perplexity.Client(cookies)

    print(f"Client created with account")
    print(f"File uploads available: {client.file_upload}")

    # Create a sample file
    sample_file = Path("sample.txt")
    sample_file.write_text("This is a sample document about artificial intelligence.")

    try:
        with open(sample_file, "r") as f:
            response = client.search("What is this document about?", files={"sample.txt": f.read()})

        if "answer" in response:
            print("\nResponse:")
            print("-" * 60)
            print(response["answer"])
            print("-" * 60)

    finally:
        # Cleanup
        if sample_file.exists():
            sample_file.unlink()

    print("\n" + "=" * 60)
    print("File upload example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
