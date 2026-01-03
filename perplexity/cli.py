"""
Typer CLI wrapper for Perplexity AI.

This module provides a command-line interface for interacting with Perplexity AI
using the typer library for an intuitive CLI experience.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

import typer
from typing_extensions import Annotated

from .client import Client
from patchright.sync_api import sync_playwright as sync_patchright
from playwright.sync_api import sync_playwright

app = typer.Typer(
    name="perplexity",
    help="Perplexity AI - Unofficial Python CLI for Perplexity.ai",
    add_completion=False,
)


def load_cookies_from_file(cookies_path: Path) -> dict:
    """Load cookies from a JSON file."""
    try:
        with open(cookies_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        typer.secho(f"Error: Cookies file not found: {cookies_path}", fg=typer.colors.RED)
        raise typer.Exit(1)
    except json.JSONDecodeError:
        typer.secho(f"Error: Invalid JSON in cookies file: {cookies_path}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query to ask Perplexity AI")],
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Search mode: auto, pro, reasoning, or deep research",
        ),
    ] = "auto",
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="Model to use (depends on mode). E.g., gpt-5.2, claude-4.5-sonnet",
        ),
    ] = None,
    sources: Annotated[
        Optional[List[str]],
        typer.Option(
            "--source",
            "-s",
            help="Information sources (can be specified multiple times): web, scholar, social",
        ),
    ] = None,
    cookies_file: Annotated[
        Optional[Path],
        typer.Option(
            "--cookies",
            "-c",
            help="Path to JSON file containing Perplexity cookies for authentication",
        ),
    ] = None,
    stream: Annotated[
        bool,
        typer.Option(
            "--stream",
            help="Enable streaming responses",
        ),
    ] = False,
    language: Annotated[
        str,
        typer.Option(
            "--language",
            "-l",
            help="Language code (ISO 639)",
        ),
    ] = "en-US",
    incognito: Annotated[
        bool,
        typer.Option(
            "--incognito",
            help="Enable incognito mode (for authenticated users)",
        ),
    ] = False,
    files: Annotated[
        Optional[List[Path]],
        typer.Option(
            "--file",
            "-f",
            help="Files to upload (can be specified multiple times)",
        ),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Save response to file instead of printing to stdout",
        ),
    ] = None,
):
    """
    Search using Perplexity AI.

    Examples:

        # Basic search
        perplexity search "What is artificial intelligence?"

        # Search with specific mode and sources
        perplexity search "Latest AI research" --mode pro --source scholar

        # Search with authentication
        perplexity search "Complex query" --cookies cookies.json --mode reasoning

        # Search with file upload
        perplexity search "Analyze this document" --file document.pdf --cookies cookies.json

        # Streaming response
        perplexity search "Explain quantum computing" --stream
    """
    # Load cookies if provided
    cookies = {}
    if cookies_file:
        cookies = load_cookies_from_file(cookies_file)

    # Prepare sources list
    if sources is None:
        sources = ["web"]

    # Prepare files dictionary
    files_dict = {}
    if files:
        for file_path in files:
            if not file_path.exists():
                typer.secho(f"Error: File not found: {file_path}", fg=typer.colors.RED)
                raise typer.Exit(1)
            try:
                with open(file_path, "rb") as f:
                    files_dict[file_path.name] = f.read()
            except Exception as e:
                typer.secho(f"Error reading file {file_path}: {e}", fg=typer.colors.RED)
                raise typer.Exit(1)

    # Create client and perform search
    try:
        typer.secho(f"🔍 Searching: {query}", fg=typer.colors.CYAN)
        if mode != "auto":
            typer.secho(f"Mode: {mode}", fg=typer.colors.YELLOW, dim=True)
        if model:
            typer.secho(f"Model: {model}", fg=typer.colors.YELLOW, dim=True)

        client = Client(cookies)

        response = client.search(
            query=query,
            mode=mode,
            model=model,
            sources=sources,
            files=files_dict,
            stream=stream,
            language=language,
            follow_up=None,
            incognito=incognito,
        )

        typer.secho("\n" + "=" * 60, fg=typer.colors.BLUE)
        typer.secho("Response:", fg=typer.colors.GREEN, bold=True)
        typer.secho("=" * 60 + "\n", fg=typer.colors.BLUE)

        if stream:
            # Handle streaming response
            answer_parts = []
            for chunk in response:
                if "answer" in chunk:
                    answer_text = chunk["answer"]
                    typer.echo(answer_text, nl=False)
                    sys.stdout.flush()
                    answer_parts.append(answer_text)
            typer.echo()  # New line after streaming

            if output:
                with open(output, "w", encoding="utf-8") as f:
                    f.write("".join(answer_parts))
                typer.secho(f"\n✓ Response saved to {output}", fg=typer.colors.GREEN)
        else:
            # Handle non-streaming response
            if "answer" in response:
                answer = response["answer"]
                typer.echo(answer)

                if output:
                    with open(output, "w", encoding="utf-8") as f:
                        json.dump(response, f, indent=2)
                    typer.secho(f"\n✓ Full response saved to {output}", fg=typer.colors.GREEN)
            else:
                typer.secho("No answer found in response", fg=typer.colors.YELLOW)
                typer.echo(json.dumps(response, indent=2))

    except AssertionError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error during search: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def create_account(
    emailnator_cookies: Annotated[
        Path,
        typer.Argument(help="Path to JSON file containing Emailnator cookies"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Save new account cookies to file",
        ),
    ] = None,
):
    """
    Create a new Perplexity account using Emailnator.

    This command creates a new account which grants you additional pro queries.
    You need Emailnator cookies to use this feature.

    Example:

        perplexity create-account emailnator_cookies.json --output new_account.json
    """
    # Load Emailnator cookies
    emailnator_cookies_dict = load_cookies_from_file(emailnator_cookies)

    try:
        typer.secho("Creating new Perplexity account...", fg=typer.colors.CYAN)

        client = Client()
        success = client.create_account(emailnator_cookies_dict)

        if success:
            typer.secho("✓ Account created successfully!", fg=typer.colors.GREEN, bold=True)
            typer.secho(f"Available pro queries: {client.copilot}", fg=typer.colors.YELLOW)
            typer.secho(f"Available file uploads: {client.file_upload}", fg=typer.colors.YELLOW)

            # Save new account cookies if output specified
            if output:
                new_cookies = client.session.cookies.get_dict()
                with open(output, "w", encoding="utf-8") as f:
                    json.dump(new_cookies, f, indent=2)
                typer.secho(f"✓ Account cookies saved to {output}", fg=typer.colors.GREEN)
        else:
            typer.secho("Failed to create account", fg=typer.colors.RED)
            raise typer.Exit(1)

    except Exception as e:
        typer.secho(f"Error creating account: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def auth(
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Save authentication cookies to file (default: perplexity_cookies.json)",
        ),
    ] = None,
    cdp_port: Annotated[
        Optional[int],
        typer.Option(
            "--cdp-port",
            "-p",
            help="Connect to Chrome via CDP on this port (recommended for reliability)",
        ),
    ] = None,
    user_data_dir: Annotated[
        Optional[str],
        typer.Option(
            "--user-data-dir",
            "-u",
            help="Chrome user data directory (used when not connecting via CDP)",
        ),
    ] = None,
):
    """
    Authenticate with Perplexity AI via browser login.

    RECOMMENDED: Use CDP to connect to an existing Chrome instance for best reliability.

    Steps for CDP (best method):
    1. Start Chrome with remote debugging:
       Chrome: chrome.exe --remote-debugging-port=9222
       Or add to Chrome shortcut: --remote-debugging-port=9222
    2. Open Perplexity.ai in that Chrome and log in manually
    3. Run: perplexity auth --cdp-port 9222

    Alternative: Use user data directory (may face Cloudflare):
       perplexity auth --user-data-dir "C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data"

    Examples:

        # Best: Connect to Chrome via CDP
        perplexity auth --cdp-port 9222

        # Alternative: Use user data directory
        perplexity auth --user-data-dir "~/.config/google-chrome"

        # Basic (not recommended - will face Cloudflare)
        perplexity auth
    """
    import os
    import tempfile
    import time
    
    if output is None:
        output = Path("perplexity_cookies.json")

    browser = None
    
    try:
        if cdp_port:
            # Connect to existing Chrome via CDP (most reliable method)
            typer.secho(f"🔌 Connecting to Chrome on CDP port {cdp_port}...", fg=typer.colors.CYAN)
            typer.secho("   Make sure Chrome is running with --remote-debugging-port", fg=typer.colors.YELLOW, dim=True)
            typer.echo()
            
            with sync_playwright() as p:
                try:
                    browser = p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
                    typer.secho("✓ Connected to Chrome successfully!", fg=typer.colors.GREEN)
                except Exception as e:
                    typer.secho(f"✗ Failed to connect to Chrome on port {cdp_port}", fg=typer.colors.RED)
                    typer.secho(f"   Error: {e}", fg=typer.colors.RED, dim=True)
                    typer.echo()
                    typer.secho("Start Chrome with:", fg=typer.colors.YELLOW)
                    typer.secho('  chrome.exe --remote-debugging-port=9222', fg=typer.colors.YELLOW, bold=True)
                    raise typer.Exit(1)
                
                # Get default context (existing browser window)
                if browser.contexts:
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else context.new_page()
                else:
                    typer.secho("✗ No browser contexts found", fg=typer.colors.RED)
                    raise typer.Exit(1)
                
                typer.secho("🌐 Using existing Chrome window...", fg=typer.colors.CYAN)
                typer.echo()
                
                # Navigate to Perplexity.ai
                current_url = page.url
                if "perplexity.ai" not in current_url:
                    typer.secho("📍 Navigating to Perplexity.ai...", fg=typer.colors.CYAN)
                    try:
                        page.goto("https://www.perplexity.ai/", wait_until="domcontentloaded", timeout=30000)
                    except Exception as e:
                        typer.secho(f"⚠ Navigation timeout (page may still be loading)", fg=typer.colors.YELLOW, dim=True)
                else:
                    typer.secho(f"✓ Already on Perplexity.ai", fg=typer.colors.GREEN, dim=True)
                
                typer.echo()
                
                # Check authentication status
                def check_auth_status():
                    """Check if user is authenticated by looking for auth cookies and UI elements"""
                    try:
                        # Check for authentication cookies
                        cookies = context.cookies()
                        has_auth_cookie = any(c["name"].startswith("next-auth") for c in cookies)
                        
                        # Check for authenticated UI elements using JavaScript
                        is_logged_in = page.evaluate("""
                            () => {
                                // Check for common authenticated UI elements
                                const hasUserMenu = document.querySelector('[data-testid="user-menu"]') !== null;
                                const hasProfileButton = document.querySelector('button[aria-label*="profile"]') !== null;
                                const hasAccountButton = document.querySelector('[aria-label*="account"]') !== null;
                                
                                // Check for Pro badge or subscription indicators
                                const hasProBadge = document.body.innerText.includes('Pro');
                                
                                return hasUserMenu || hasProfileButton || hasAccountButton;
                            }
                        """)
                        
                        return has_auth_cookie or is_logged_in
                    except Exception:
                        return False
                
                # Check current authentication status
                typer.secho("🔍 Checking authentication status...", fg=typer.colors.CYAN)
                
                is_authenticated = check_auth_status()
                
                if is_authenticated:
                    typer.secho("✓ Already authenticated!", fg=typer.colors.GREEN, bold=True)
                else:
                    typer.secho("⚠ Not authenticated yet", fg=typer.colors.YELLOW)
                    typer.secho("   Please log in to Perplexity in the browser", fg=typer.colors.YELLOW)
                    typer.echo()
                    typer.secho("⏳ Waiting for login... Press Ctrl+C when done", fg=typer.colors.YELLOW, bold=True)
                
                typer.echo()
                
                # Wait for authentication or user interrupt
                interrupted = False
                auto_saved = False
                try:
                    # Check authentication status periodically
                    max_checks = 120  # 2 minutes max (check every second)
                    for i in range(max_checks):
                        if not is_authenticated:
                            # Check if user has logged in
                            is_authenticated = check_auth_status()
                            if is_authenticated:
                                typer.secho("\n✓ Login detected!", fg=typer.colors.GREEN, bold=True)
                                # Auto-save after detecting login
                                time.sleep(1)  # Wait a moment for cookies to propagate
                                auto_saved = True
                                break
                        else:
                            # Already authenticated, auto-save immediately
                            if i == 0:
                                typer.secho("💾 Saving cookies automatically...", fg=typer.colors.CYAN)
                                auto_saved = True
                            break
                        
                        time.sleep(1)
                        
                except KeyboardInterrupt:
                    typer.echo()
                    interrupted = True
                
                # Get cookies
                typer.secho("📦 Retrieving cookies...", fg=typer.colors.CYAN, dim=True)
                try:
                    cookies = context.cookies()
                    cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
                except Exception as e:
                    typer.secho(f"✗ Error getting cookies: {e}", fg=typer.colors.RED)
                    cookies_dict = {}
                
                # Save cookies immediately within context manager (for CDP)
                if cookies_dict:
                    # Check and save cookies
                    has_auth = any(key.startswith("next-auth") for key in cookies_dict.keys())
                    
                    with open(output, "w", encoding="utf-8") as f:
                        json.dump(cookies_dict, f, indent=2)
                    
                    if has_auth:
                        typer.secho(f"\n✓ Authentication successful!", fg=typer.colors.GREEN, bold=True)
                        typer.secho(f"✓ Cookies saved to {output}", fg=typer.colors.GREEN)
                        typer.echo()
                        typer.secho(f"You can now use:", fg=typer.colors.CYAN)
                        typer.secho(f'  perplexity search "your query" --cookies {output}', fg=typer.colors.CYAN, bold=True)
                    else:
                        typer.secho(f"\n⚠ Cookies saved to {output}", fg=typer.colors.YELLOW)
                        typer.secho("   Note: No authentication cookies found. You may need to log in first.", fg=typer.colors.YELLOW, dim=True)
                else:
                    typer.secho("\n⚠ No cookies found. Please try again.", fg=typer.colors.YELLOW)
                    
                if interrupted:
                    raise KeyboardInterrupt
                
                # Exit successfully for CDP case (return to avoid exception handler)
                return
                
        else:
            # Fallback to persistent context (less reliable)
            if user_data_dir is None:
                temp_dir = tempfile.mkdtemp(prefix="perplexity_chrome_")
                user_data_dir = temp_dir
                typer.secho("⚠ No CDP port or user data directory provided.", fg=typer.colors.YELLOW)
                typer.secho("  This will likely face Cloudflare protection!", fg=typer.colors.YELLOW, bold=True)
                typer.secho("  RECOMMENDED: Use --cdp-port 9222 instead", fg=typer.colors.YELLOW, dim=True)
                typer.echo()
            else:
                typer.secho(f"✓ Using Chrome profile: {user_data_dir}", fg=typer.colors.GREEN, dim=True)
                typer.echo()

            typer.secho("🌐 Opening browser for authentication...", fg=typer.colors.CYAN)
            typer.echo()

            with sync_patchright() as p:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="chrome",
                    headless=False,
                    no_viewport=True,
                )
                
                page = browser.new_page()
                
                typer.secho("🔄 Loading Perplexity.ai...", fg=typer.colors.CYAN, dim=True)
                page.goto("https://www.perplexity.ai/", wait_until="networkidle")

                typer.secho("⏳ Waiting for you to complete login...", fg=typer.colors.YELLOW)
                typer.secho("   Press Ctrl+C when you're done to save and exit.\n", fg=typer.colors.YELLOW, dim=True)

                try:
                    # Wait in small increments to allow clean interrupt
                    for _ in range(600):  # 10 minutes max (600 seconds)
                        time.sleep(1)
                except KeyboardInterrupt:
                    typer.echo()
                except Exception:
                    pass

                cookies = browser.cookies()
                cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
                browser.close()

        # Check and save cookies
        if cookies_dict and any(key.startswith("next-auth") for key in cookies_dict.keys()):
            with open(output, "w", encoding="utf-8") as f:
                json.dump(cookies_dict, f, indent=2)

            typer.secho(f"✓ Authentication successful!", fg=typer.colors.GREEN, bold=True)
            typer.secho(f"✓ Cookies saved to {output}", fg=typer.colors.GREEN)
            typer.echo()
            typer.secho(f"You can now use:", fg=typer.colors.CYAN)
            typer.secho(f'  perplexity search "your query" --cookies {output}', fg=typer.colors.CYAN, bold=True)
        elif cookies_dict:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(cookies_dict, f, indent=2)
            typer.secho(f"\n⚠ Cookies saved to {output}", fg=typer.colors.YELLOW)
            typer.secho("   Note: Login may not be complete. Try using the cookies and re-authenticate if needed.", fg=typer.colors.YELLOW, dim=True)
        else:
            typer.secho("\n⚠ No cookies found. Please try again.", fg=typer.colors.YELLOW)
            raise typer.Exit(1)

    except KeyboardInterrupt:
        typer.secho("\n✓ Saving cookies and exiting...", fg=typer.colors.GREEN)
        try:
            # Only handle if browser is still accessible (non-CDP case)
            # For CDP, cookies are already saved within the context manager
            if browser and not cdp_port:
                try:
                    cookies = browser.cookies()
                    cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
                    if cookies_dict:
                        with open(output, "w", encoding="utf-8") as f:
                            json.dump(cookies_dict, f, indent=2)
                        typer.secho(f"✓ Cookies saved to {output}", fg=typer.colors.GREEN)
                    browser.close()
                except Exception as e:
                    typer.secho(f"Warning: {e}", fg=typer.colors.YELLOW, dim=True)
        except Exception as e:
            typer.secho(f"Warning: {e}", fg=typer.colors.YELLOW, dim=True)
        raise typer.Exit(0)
    except Exception as e:
        typer.secho(f"\n✗ Error during authentication: {e}", fg=typer.colors.RED)
        if browser and not cdp_port:
            try:
                browser.close()
            except:
                pass
        raise typer.Exit(1)


@app.command()
def info():
    """
    Display information about available modes and models.
    """
    typer.secho("Perplexity AI - Available Options", fg=typer.colors.CYAN, bold=True)
    typer.echo()

    typer.secho("Search Modes:", fg=typer.colors.GREEN, bold=True)
    modes = {
        "auto": "Automatic mode (free)",
        "pro": "Pro mode (requires account with pro queries)",
        "reasoning": "Reasoning mode (requires account with pro queries)",
        "deep research": "Deep research mode (requires account with pro queries)",
    }
    for mode, description in modes.items():
        typer.echo(f"  • {mode}: {description}")

    typer.echo()
    typer.secho("Available Models by Mode:", fg=typer.colors.GREEN, bold=True)

    models_by_mode = {
        "auto": [None],
        "pro": [None, "sonar", "gpt-5.2", "claude-4.5-sonnet", "grok-4-1"],
        "reasoning": [
            None,
            "gpt-5.2-thinking",
            "claude-4.5-sonnet-thinking",
            "gemini-3.0-pro",
            "kimi-k2-thinking",
            "grok-4.1-reasoning",
        ],
        "deep research": [None],
    }

    for mode, models in models_by_mode.items():
        typer.echo(f"\n  {mode}:")
        for model in models:
            if model is None:
                typer.echo(f"    • default")
            else:
                typer.echo(f"    • {model}")

    typer.echo()
    typer.secho("Information Sources:", fg=typer.colors.GREEN, bold=True)
    sources = ["web", "scholar", "social"]
    for source in sources:
        typer.echo(f"  • {source}")

    typer.echo()
    typer.secho(
        "For more information, visit: https://github.com/ESousa97/perplexity-ai",
        fg=typer.colors.BLUE,
    )


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
