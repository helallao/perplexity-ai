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
