#!/usr/bin/env python3
"""Implementation verification helper for the Perplexity AI project."""

from __future__ import annotations

from pathlib import Path
import sys


class Colors:
    """ANSI escape sequences used to format terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Render a section header."""

    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_test(name: str, passed: bool) -> bool:
    """Print the outcome of a single check."""

    status = (
        f"{Colors.GREEN}[PASS]{Colors.RESET}"
        if passed
        else f"{Colors.RED}[FAIL]{Colors.RESET}"
    )
    print(f"{status} {name}")
    return passed


def print_summary(total: int, passed: int) -> None:
    """Summarize the verification session."""

    failed = total - passed
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}VERIFICATION SUMMARY{Colors.RESET}")
    print(f"{'=' * 70}")
    print(f"Total checks: {total}")
    print(f"{Colors.GREEN}Passing: {passed}{Colors.RESET}")
    if failed > 0:
        print(f"{Colors.RED}Failing: {failed}{Colors.RESET}")
    print(f"Success rate: {percentage:.1f}%")
    print(f"{'=' * 70}\n")


def main() -> int:
    """Execute the full verification workflow."""

    print_header("IMPLEMENTATION VERIFICATION - PERPLEXITY AI")

    results: list[bool] = []

    # 1. FILE STRUCTURE
    print_header("1. CHECKING FILE STRUCTURE")

    files_to_check = [
        # Infrastructure
        ("perplexity/config.py", "Configuration module"),
        ("perplexity/logger.py", "Logging module"),
        ("perplexity/exceptions.py", "Custom exceptions"),
        ("perplexity/utils.py", "Utilities"),
        ("pyproject.toml", "Build configuration"),
        # Tests
        ("tests/__init__.py", "Test package initializer"),
        ("tests/test_utils.py", "Utility tests"),
        ("tests/test_config.py", "Config tests"),
        # Examples
        ("examples/basic_usage.py", "Basic example"),
        ("examples/streaming.py", "Streaming example"),
        ("examples/async_usage.py", "Async example"),
        ("examples/file_upload.py", "File upload example"),
        ("examples/account_creation.py", "Account creation example"),
        ("examples/batch_processing.py", "Batch processing example"),
        ("examples/README.md", "Examples README"),
        # CI/CD
        (".github/workflows/test.yml", "Test workflow"),
        (".github/workflows/quality.yml", "Quality workflow"),
        (".github/workflows/publish.yml", "Publish workflow"),
        # Documentation
        ("docs/CHANGELOG.md", "Changelog"),
        ("docs/IMPROVEMENTS.md", "Improvements list"),
        ("docs/NEXT_STEPS.md", "Next steps guide"),
        ("docs/IMPLEMENTATION_SUMMARY.md", "Implementation summary"),
        ("docs/CONCLUSION.md", "Project conclusion"),
    ]

    for filepath, description in files_to_check:
        exists = Path(filepath).exists()
        results.append(print_test(f"{description} ({filepath})", exists))

    # 2. IMPORTS
    print_header("2. CHECKING IMPORTS")

    try:
        from perplexity.config import API_BASE_URL, SEARCH_MODES

        results.append(print_test("config.py imports", True))
    except Exception as exc:  # pragma: no cover - diagnostic output only
        results.append(print_test(f"config.py imports - Error: {exc}", False))

    try:
        from perplexity.logger import logger

        results.append(print_test("logger.py imports", True))
    except Exception as exc:  # pragma: no cover
        results.append(print_test(f"logger.py imports - Error: {exc}", False))

    try:
        from perplexity.exceptions import PerplexityError, ValidationError

        results.append(print_test("exceptions.py imports", True))
    except Exception as exc:  # pragma: no cover
        results.append(
            print_test(f"exceptions.py imports - Error: {exc}", False)
        )

    try:
        from perplexity.utils import (
            retry_with_backoff,
            sanitize_query,
            validate_search_params,
        )

        results.append(print_test("utils.py imports", True))
    except Exception as exc:  # pragma: no cover
        results.append(print_test(f"utils.py imports - Error: {exc}", False))

    # 3. FUNCTIONAL BEHAVIOR
    print_header("3. CHECKING FUNCTIONAL BEHAVIOR")

    try:
        assert API_BASE_URL == "https://www.perplexity.ai"
        assert "auto" in SEARCH_MODES
        assert "pro" in SEARCH_MODES
        results.append(print_test("Configuration values", True))
    except Exception as exc:
        results.append(
            print_test(f"Configuration values - Error: {exc}", False)
        )

    try:
        logger.info("Verification log message")
        results.append(print_test("Logger writes", True))
    except Exception as exc:
        results.append(print_test(f"Logger - Error: {exc}", False))

    try:
        assert issubclass(ValidationError, PerplexityError)
        results.append(print_test("Exception hierarchy", True))
    except Exception as exc:
        results.append(
            print_test(f"Exception hierarchy - Error: {exc}", False)
        )

    try:
        # Sanitize keeps trimmed value
        cleaned = sanitize_query("  test query  ")
        assert cleaned == "test query"

        # Valid parameters should pass
        validate_search_params("auto", None, ["web"], False)

        # Invalid mode should fail
        try:
            validate_search_params("invalid", None, ["web"], False)
            results.append(print_test("Validation helpers", False))
        except ValidationError:
            results.append(print_test("Validation helpers", True))
    except Exception as exc:
        results.append(print_test(f"Validation helpers - Error: {exc}", False))

    try:
        call_count = [0]

        @retry_with_backoff(max_attempts=3, backoff_factor=0.01)
        def test_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Transient error")
            return "success"

        result = test_func()
        assert result == "success"
        assert call_count[0] == 2
        results.append(print_test("Retry decorator", True))
    except Exception as exc:
        results.append(print_test(f"Retry decorator - Error: {exc}", False))

    # 4. EXAMPLE SYNTAX
    print_header("4. CHECKING EXAMPLE SYNTAX")

    example_files = [
        "examples/basic_usage.py",
        "examples/streaming.py",
        "examples/async_usage.py",
        "examples/file_upload.py",
        "examples/account_creation.py",
        "examples/batch_processing.py",
    ]

    for example in example_files:
        try:
            with open(example, "r", encoding="utf-8") as handle:
                code = handle.read()
                compile(code, example, "exec")
            results.append(
                print_test(f"Syntax OK for {Path(example).name}", True)
            )
        except Exception as exc:
            results.append(
                print_test(
                    f"Syntax error in {Path(example).name}: {exc}", False
                )
            )

    # 5. DOCUMENTATION
    print_header("5. CHECKING DOCUMENTATION")

    try:
        with open("README.md", "r", encoding="utf-8") as handle:
            readme = handle.read()
            checks = [
                (
                    "Test badge",
                    "workflows/Tests/badge.svg" in readme
                    or "![Tests]" in readme,
                ),
                ("Installation section", "## Installation" in readme),
                ("Examples section", "examples/" in readme.lower()),
                ("API reference", "API Reference" in readme),
                ("Quick start", "Quick Start" in readme),
            ]

            for check_name, check_result in checks:
                results.append(
                    print_test(f"README includes {check_name}", check_result)
                )
    except Exception as exc:
        results.append(
            print_test(f"README verification - Error: {exc}", False)
        )

    doc_checks = [
        ("docs/CHANGELOG.md", "Bug #1"),
        ("docs/IMPROVEMENTS.md", "Suggested Improvements"),
        ("docs/NEXT_STEPS.md", "Next Steps Guide"),
        ("docs/IMPLEMENTATION_SUMMARY.md", "Implementation Summary"),
        ("docs/CONCLUSION.md", "Project Completion"),
    ]

    for doc_file, keyword in doc_checks:
        try:
            with open(doc_file, "r", encoding="utf-8") as handle:
                content = handle.read()
                results.append(
                    print_test(
                        f"{doc_file} includes '{keyword}'", keyword in content
                    )
                )
        except Exception as exc:
            results.append(print_test(f"{doc_file} - Error: {exc}", False))

    # 6. CI/CD
    print_header("6. CHECKING CI/CD WORKFLOWS")

    workflow_checks = [
        (".github/workflows/test.yml", ["pytest", "matrix", "python-version"]),
        (".github/workflows/quality.yml", ["black", "flake8", "mypy"]),
        (".github/workflows/publish.yml", ["PyPI", "twine", "build"]),
    ]

    for workflow_file, keywords in workflow_checks:
        try:
            with open(workflow_file, "r", encoding="utf-8") as handle:
                content = handle.read()
                all_present = all(keyword in content for keyword in keywords)
                keywords_label = ", ".join(keywords)
                message = (
                    f"{Path(workflow_file).name} includes "
                    f"{keywords_label}"
                )
                results.append(print_test(message, all_present))
        except Exception as exc:
            results.append(
                print_test(f"{workflow_file} - Error: {exc}", False)
            )

    # SUMMARY
    total = len(results)
    passed = sum(results)

    print_summary(total, passed)

    if passed == total:
        print(
            f"{Colors.GREEN}{Colors.BOLD}IMPLEMENTATION VERIFIED{Colors.RESET}"
        )
        print("All checks passed. The project is ready for use.\n")
        return 0

    success_ratio = passed / total if total else 0
    if success_ratio >= 0.8:
        print(
            f"{Colors.YELLOW}{Colors.BOLD}VERIFICATION PARTIALLY PASSING"
            f"{Colors.RESET}"
        )
        print(
            f"Passing checks: {passed}/{total}. Review the failures above.\n"
        )
        return 1

    print(f"{Colors.RED}{Colors.BOLD}VERIFICATION FAILED{Colors.RESET}")
    print(
        f"Failing checks: {total - passed}/{total}. "
        "Address the issues above.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
