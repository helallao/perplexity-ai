# Perplexity CLI Documentation

The Perplexity CLI provides a command-line interface for interacting with Perplexity AI. It's built with [Typer](https://typer.tiangolo.com/) for an intuitive and user-friendly experience.

## Installation

```bash
pip install -e .
```

After installation, the `perplexity` command will be available globally.

## Quick Start

```bash
# Get help
perplexity --help

# Basic search
perplexity search "What is artificial intelligence?"

# View available modes and models
perplexity info
```

## Commands

### `search`

Search using Perplexity AI with various modes and options.

#### Basic Usage

```bash
perplexity search "Your query here"
```

#### Options

- `--mode, -m`: Search mode
  - `auto` (default): Automatic mode (free)
  - `pro`: Pro mode (requires account with pro queries)
  - `reasoning`: Reasoning mode (requires account with pro queries)
  - `deep research`: Deep research mode (requires account with pro queries)

- `--model`: Specific model to use (depends on mode)
  - Pro models: `sonar`, `gpt-5.2`, `claude-4.5-sonnet`, `grok-4-1`
  - Reasoning models: `gpt-5.2-thinking`, `claude-4.5-sonnet-thinking`, `gemini-3.0-pro`, `kimi-k2-thinking`, `grok-4.1-reasoning`

- `--source, -s`: Information sources (can be specified multiple times)
  - `web` (default)
  - `scholar` (academic papers)
  - `social` (social media)

- `--cookies, -c`: Path to JSON file containing Perplexity cookies for authentication

- `--stream`: Enable streaming responses (display results as they arrive)

- `--language, -l`: Language code (ISO 639), default: `en-US`

- `--incognito`: Enable incognito mode (for authenticated users)

- `--file, -f`: Files to upload (can be specified multiple times)

- `--output, -o`: Save response to file instead of printing to stdout

#### Examples

```bash
# Basic search
perplexity search "What is artificial intelligence?"

# Search with specific mode and sources
perplexity search "Latest AI research 2024" --mode pro --source scholar

# Search with authentication (requires cookies file)
perplexity search "Complex query" --cookies cookies.json --mode reasoning

# Search with file upload
perplexity search "Analyze this document" --file document.pdf --cookies cookies.json

# Streaming response
perplexity search "Explain quantum computing" --stream

# Multiple sources
perplexity search "Recent developments in AI" --source web --source scholar

# Save response to file
perplexity search "Quantum computing" --output response.txt

# Different language
perplexity search "¿Qué es la inteligencia artificial?" --language es-ES

# Reasoning mode with specific model
perplexity search "Solve this math problem: ..." --mode reasoning --model gpt-5.2-thinking --cookies cookies.json
```

### `create-account`

Create a new Perplexity account using Emailnator to get additional pro queries.

#### Usage

```bash
perplexity create-account emailnator_cookies.json --output new_account.json
```

#### Arguments

- `emailnator_cookies`: Path to JSON file containing Emailnator cookies (required)

#### Options

- `--output, -o`: Save new account cookies to file

#### Example

```bash
# Create account and save cookies
perplexity create-account emailnator_cookies.json --output my_account.json

# Use the new account for searches
perplexity search "Pro query" --cookies my_account.json --mode pro
```

### `info`

Display information about available modes, models, and sources.

#### Usage

```bash
perplexity info
```

This command shows:
- All available search modes
- Models available for each mode
- Information sources

## Authentication

### Getting Perplexity Cookies

1. Open [Perplexity.ai](https://perplexity.ai/) and log in to your account
2. Press F12 or Ctrl+Shift+I to open developer tools
3. Go to the "Network" tab
4. Refresh the page
5. Right-click the first request → "Copy" → "Copy as cURL (bash)"
6. Go to [CurlConverter](https://curlconverter.com/python/)
7. Paste your cURL command
8. Copy the cookies dictionary
9. Save it as a JSON file (e.g., `cookies.json`)

Example cookies.json:
```json
{
  "next-auth.csrf-token": "your-token",
  "next-auth.session-token": "your-session"
}
```

### Getting Emailnator Cookies

1. Open [Emailnator.com](https://emailnator.com/) and verify you're human
2. Follow the same process as above (F12 → Network → Refresh → Copy as cURL)
3. Convert and save as `emailnator_cookies.json`

Note: Emailnator cookies expire frequently and need to be refreshed.

## Advanced Usage

### Using with Scripts

You can integrate the CLI into shell scripts:

```bash
#!/bin/bash

# Search and save result
perplexity search "What's the weather?" --output weather.txt

# Process the result
cat weather.txt
```

### Combining Multiple Queries

```bash
# Ask multiple questions
perplexity search "What is AI?" --output ai.txt
perplexity search "What is ML?" --output ml.txt
perplexity search "What is DL?" --output dl.txt
```

### Using with Pipes

```bash
# Stream to other tools
perplexity search "Python tips" --stream | grep "tip"
```

## Error Handling

The CLI provides clear error messages:

- Invalid mode: `Error: Invalid search mode.`
- No cookies file: `Error: Cookies file not found: cookies.json`
- Invalid JSON: `Error: Invalid JSON in cookies file`
- File not found: `Error: File not found: document.pdf`
- Network errors: `Error during search: [error details]`

## Tips

1. **Use streaming for long responses**: Add `--stream` for real-time output
2. **Save responses**: Use `--output` to save results for later analysis
3. **Use scholar sources for research**: `--source scholar` for academic papers
4. **Create accounts for pro features**: Use `create-account` to get pro queries
5. **Specify models for better results**: Use `--model` with appropriate mode

## Environment

The CLI respects the following:
- Standard output for results
- Standard error for error messages
- Exit code 0 for success, 1 for errors

## See Also

- [Main README](../README.md) - General project documentation
- [Examples](../examples/) - Python API examples
- [Changelog](CHANGELOG.md) - Version history
