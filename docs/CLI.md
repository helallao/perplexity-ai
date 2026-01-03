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

### `auth`

Authenticate with Perplexity AI via browser login. This is the easiest way to get authentication cookies.

#### Usage

```bash
# BEST: Connect to Chrome via CDP (most reliable)
perplexity auth --cdp-port 9222

# Alternative: Use Chrome profile
perplexity auth --user-data-dir "~/.config/google-chrome"

# Not recommended: Basic (will face Cloudflare)
perplexity auth
```

#### How it Works - CDP Method (Recommended)

The CDP (Chrome DevTools Protocol) method is the most reliable:

1. **Start Chrome with remote debugging**:
   ```bash
   # Windows
   chrome.exe --remote-debugging-port=9222
   
   # Linux/Mac
   google-chrome --remote-debugging-port=9222
   
   # Or add to Chrome shortcut: --remote-debugging-port=9222
   ```

2. **Log in to Perplexity manually** in that Chrome window

3. **Run the auth command**:
   ```bash
   perplexity auth --cdp-port 9222
   ```

4. **Press Ctrl+C** to save cookies and exit

**Advantages of CDP:**
- ✅ No Cloudflare protection issues
- ✅ Uses your real browser session
- ✅ No browser detection
- ✅ Most reliable method
- ✅ Can keep Chrome open after saving cookies

#### Options

- `--output, -o`: Save authentication cookies to file (default: `perplexity_cookies.json`)
- `--cdp-port, -p`: Connect to Chrome via CDP on this port (recommended)
- `--user-data-dir, -u`: Path to Chrome user data directory (alternative method)

#### Examples

```bash
# RECOMMENDED: CDP method
# Step 1: Start Chrome with debugging
chrome.exe --remote-debugging-port=9222

# Step 2: Connect and save cookies
perplexity auth --cdp-port 9222

# Alternative: User data directory (Windows)
perplexity auth --user-data-dir "C:\Users\YourName\AppData\Local\Google\Chrome\User Data"

# Alternative: User data directory (Linux)
perplexity auth --user-data-dir ~/.config/google-chrome

# Custom output file
perplexity auth --cdp-port 9222 --output my_cookies.json

# Use the saved cookies
perplexity search "Complex query" --cookies my_cookies.json --mode pro
```

#### Troubleshooting CDP Connection

If `--cdp-port` fails to connect:

1. **Make sure Chrome is running** with the debug port
2. **Check the port number** matches (default 9222)
3. **Try this command** to verify Chrome is listening:
   ```bash
   curl http://localhost:9222/json/version
   ```
4. **No other debugger** should be connected (VS Code, etc.)

#### Notes

- **CDP is the recommended method** - works like the existing driver.py
- Uses regular playwright for CDP, patchright for persistent context
- Cookies remain valid for an extended period
- CDP doesn't close your Chrome - you can keep using it
- User data directory requires Chrome to be closed first

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

### Method 1: Using `perplexity auth` with CDP (Recommended)

The CDP (Chrome DevTools Protocol) method is the most reliable and bypasses all Cloudflare issues:

**Step 1: Start Chrome with remote debugging**
```bash
# Windows
chrome.exe --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

**Step 2: Log in to Perplexity** in that Chrome window manually

**Step 3: Run auth command**
```bash
perplexity auth --cdp-port 9222
```

**Step 4: Press Ctrl+C** to save cookies

This method:
1. Connects to your real Chrome browser via CDP
2. Uses your actual browser session (no Cloudflare issues)
3. Extracts cookies from the real logged-in session
4. Works 100% reliably - same as driver.py approach

**Advantages:**
- ✅ No Cloudflare protection
- ✅ No browser detection
- ✅ Uses real browser session
- ✅ Most reliable method
- ✅ Keep Chrome open after

### Method 2: Manual Cookie Export

#### Getting Perplexity Cookies

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

### Method 3: Programmatic Account Creation

#### Getting Emailnator Cookies

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

## Troubleshooting

### Cloudflare Protection / "Checking your browser" Loop

**Problem**: Browser gets stuck on "Checking your browser before accessing perplexity.ai"

**Solution 1 (BEST)**: Use CDP to connect to your real Chrome:

```bash
# Step 1: Start Chrome with debugging
chrome.exe --remote-debugging-port=9222

# Step 2: Log in to Perplexity manually in that Chrome

# Step 3: Extract cookies
perplexity auth --cdp-port 9222
```

**Solution 2**: Use user data directory (requires Chrome to be closed):

```bash
# Windows
perplexity auth --user-data-dir "C:\Users\YourName\AppData\Local\Google\Chrome\User Data"

# Linux
perplexity auth --user-data-dir ~/.config/google-chrome
```

### CDP Connection Failed

**Problem**: `Failed to connect to Chrome on port 9222`

**Solution**:
1. Make sure Chrome is running with `--remote-debugging-port=9222`
2. Verify Chrome is listening:
   ```bash
   curl http://localhost:9222/json/version
   ```
3. Close other debuggers (VS Code, DevTools)
4. Try a different port (9223, 9224, etc.)

### Google "Untrusted" Warnings

**Problem**: Browser shows warnings about untrusted or automated browser

**Solution**: Use CDP method - it connects to your real Chrome, not an automated one.

### No Cookies Saved

**Problem**: Command completes but no cookies are saved

**Solution**: 
1. Make sure you're logged in to Perplexity
2. Wait for the page to fully load
3. Press Ctrl+C to force save
4. Check if `next-auth` cookies exist in saved file

### Browser Doesn't Open (persistent context method)

**Problem**: Command runs but no browser window appears

**Solution**:
1. Make sure Chrome is installed
2. Install chromium for patchright: `patchright install chromium`
3. Try CDP method instead (more reliable)

## Tips

1. **Use streaming for long responses**: Add `--stream` for real-time output
2. **Save responses**: Use `--output` to save results for later analysis
3. **Use scholar sources for research**: `--source scholar` for academic papers
4. **Create accounts for pro features**: Use `create-account` to get pro queries
5. **Specify models for better results**: Use `--model` with appropriate mode
6. **Always use --user-data-dir for auth**: Prevents Cloudflare and detection issues

## Environment

The CLI respects the following:
- Standard output for results
- Standard error for error messages
- Exit code 0 for success, 1 for errors

## See Also

- [Main README](../README.md) - General project documentation
- [Examples](../examples/) - Python API examples
- [Changelog](CHANGELOG.md) - Version history
