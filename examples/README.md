# Perplexity AI - Examples

This directory contains practical examples demonstrating various features of the Perplexity AI library.

## Available Examples

### 1. Basic Usage (`basic_usage.py`)
The simplest way to get started with the library.
- Creating a client
- Making basic queries
- Using different sources (web, scholar, social)

```bash
python examples/basic_usage.py
```

### 2. Streaming (`streaming.py`)
Receive responses in real-time as they are generated.
- Stream response chunks
- Progress tracking
- Real-time display

```bash
python examples/streaming.py
```

### 3. Async Usage (`async_usage.py`)
Non-blocking operations for better performance.
- Single async queries
- Multiple concurrent queries
- Async streaming

```bash
python examples/async_usage.py
```

### 4. File Upload (`file_upload.py`)
Upload documents for analysis and Q&A.
- Text file upload
- PDF upload
- Multiple file upload
- Requires account with cookies

```bash
python examples/file_upload.py
```

### 5. Account Creation (`account_creation.py`)
Automatically create accounts for unlimited queries.
- Create accounts via Emailnator
- Access enhanced modes (pro, reasoning)
- Requires Emailnator cookies

```bash
python examples/account_creation.py
```

### 6. Batch Processing (`batch_processing.py`)
Process multiple queries efficiently.
- Sequential vs concurrent processing
- Performance comparison
- Async batch operations

```bash
python examples/batch_processing.py
```

## Requirements

Most examples work without any setup. Some advanced examples require:

- **File Upload & Account Creation**: Perplexity account cookies
- **Batch Processing**: Python 3.8+ with asyncio support

## Getting Cookies

### Perplexity Cookies (for file upload)
1. Open [Perplexity.ai](https://perplexity.ai/) and login
2. Press F12 to open DevTools
3. Go to Network tab
4. Refresh page
5. Right-click first request → Copy → Copy as cURL (bash)
6. Paste at [CurlConverter.com](https://curlconverter.com/python/)
7. Copy the cookies dictionary

### Emailnator Cookies (for account creation)
1. Open [Emailnator.com](https://emailnator.com/)
2. Complete verification
3. Press F12 to open DevTools
4. Go to Network tab
5. Refresh page
6. Right-click first request → Copy → Copy as cURL (bash)
7. Paste at [CurlConverter.com](https://curlconverter.com/python/)
8. Copy the cookies dictionary

Note: Emailnator cookies expire frequently and need renewal.

## Tips

- Start with `basic_usage.py` to understand fundamentals
- Use `async_usage.py` for production applications
- `batch_processing.py` shows 3-5x performance improvement
- Always handle errors in production code

## Next Steps

After running examples:
1. Read the [documentation](../docs/)
2. Check the [API reference](../README.md)
3. Explore [advanced features](../docs/IMPROVEMENTS.md)
