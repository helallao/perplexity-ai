#!/bin/bash
# Example: Using Perplexity CLI
# This script demonstrates various CLI commands

echo "=== Perplexity CLI Examples ==="
echo ""

echo "1. Getting help"
perplexity --help
echo ""

echo "2. Viewing available modes and models"
perplexity info
echo ""

echo "3. Authenticate using CDP (RECOMMENDED - most reliable)"
echo "Command: chrome.exe --remote-debugging-port=9222  # Start Chrome first"
echo "Command: perplexity auth --cdp-port 9222          # Then save cookies"
echo "This connects to your real Chrome session - no Cloudflare issues!"
# chrome.exe --remote-debugging-port=9222
# perplexity auth --cdp-port 9222
echo ""

echo "4. Basic search (this would work if we had network access)"
echo "Command: perplexity search \"What is artificial intelligence?\""
# perplexity search "What is artificial intelligence?"
echo ""

echo "5. Search with authentication for pro features"
echo "Command: perplexity search \"Latest AI research\" --mode pro --source scholar --cookies my_cookies.json"
# perplexity search "Latest AI research" --mode pro --source scholar --cookies my_cookies.json
echo ""

echo "6. Search with streaming"
echo "Command: perplexity search \"Explain quantum computing\" --stream"
# perplexity search "Explain quantum computing" --stream
echo ""

echo "7. Search with file upload"
echo "Command: perplexity search \"Analyze this document\" --file document.pdf --cookies my_cookies.json"
# perplexity search "Analyze this document" --file document.pdf --cookies my_cookies.json
echo ""

echo "8. Create account (alternative method using Emailnator cookies)"
echo "Command: perplexity create-account emailnator_cookies.json --output account.json"
# perplexity create-account emailnator_cookies.json --output account.json
echo ""

echo "=== Examples complete ==="
echo ""
echo "Note: Some commands are commented out because they require network access"
echo "and authentication. Uncomment them to try in your environment."
