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

echo "3. Basic search (this would work if we had network access)"
echo "Command: perplexity search \"What is artificial intelligence?\""
# perplexity search "What is artificial intelligence?"
echo ""

echo "4. Search with specific mode and sources"
echo "Command: perplexity search \"Latest AI research\" --mode pro --source scholar"
# perplexity search "Latest AI research" --mode pro --source scholar
echo ""

echo "5. Search with streaming"
echo "Command: perplexity search \"Explain quantum computing\" --stream"
# perplexity search "Explain quantum computing" --stream
echo ""

echo "6. Search with file upload"
echo "Command: perplexity search \"Analyze this document\" --file document.pdf --cookies cookies.json"
# perplexity search "Analyze this document" --file document.pdf --cookies cookies.json
echo ""

echo "7. Create account (requires Emailnator cookies)"
echo "Command: perplexity create-account emailnator_cookies.json --output account.json"
# perplexity create-account emailnator_cookies.json --output account.json
echo ""

echo "=== Examples complete ==="
echo ""
echo "Note: Some commands are commented out because they require network access"
echo "and authentication. Uncomment them to try in your environment."
