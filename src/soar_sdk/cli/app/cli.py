from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(
    help="Commands for SOAR app development and testing",
)

console = Console()


@app.command()
def test(
    app_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the app directory",
        ),
    ] = Path("."),
    parallel: Annotated[
        bool,
        typer.Option(
            "--parallel/--no-parallel",
            "-p",
            help="Run tests in parallel using pytest-xdist",
        ),
    ] = True,
    coverage: Annotated[
        bool,
        typer.Option(
            "--coverage",
            "-c",
            help="Run with coverage reporting",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Verbose test output",
        ),
    ] = False,
    test_path: Annotated[
        Path | None,
        typer.Option(
            "--test-path",
            "-t",
            help="Path to specific test file or directory within the app",
        ),
    ] = None,
    junit_xml: Annotated[
        Path | None,
        typer.Option(
            "--junit-xml",
            help="Path to save JUnit XML test results",
        ),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            "-w",
            help="Watch mode - re-run tests on file changes",
        ),
    ] = False,
) -> None:
    """Run tests for a SOAR app.

    This command runs pytest tests for a SOAR app built with the SDK.
    It automatically discovers tests in the app's test directory.

    By default, it looks for tests in these locations:
    - tests/
    - test/
    - src/tests/
    - Any files matching test_*.py or *_test.py

    Examples:
        # Run tests in current app directory
        soarapps app test

        # Run tests for specific app
        soarapps app test ./my_app

        # Run with coverage
        soarapps app test --coverage

        # Run specific test file
        soarapps app test -t tests/test_actions.py

        # Watch mode for development
        soarapps app test --watch
    """
    if not app_path.exists():
        console.print(f"[red]Error: App directory not found: {app_path}[/red]")
        raise typer.Exit(1)

    if not app_path.is_dir():
        console.print(f"[red]Error: {app_path} is not a directory[/red]")
        raise typer.Exit(1)

    pyproject_path = app_path / "pyproject.toml"
    if not pyproject_path.exists():
        console.print(
            f"[yellow]Warning: No pyproject.toml found in {app_path}. "
            "This may not be a valid SOAR app.[/yellow]"
        )

    if watch:
        pytest_cmd = "pytest-watch"
        pytest_args = ["uv", "run", "ptw"]
    else:
        pytest_cmd = "pytest"
        pytest_args = ["uv", "run", "pytest"]

    if test_path:
        test_target = app_path / test_path
        if not test_target.exists():
            console.print(f"[red]Error: Test path not found: {test_target}[/red]")
            raise typer.Exit(1)
        pytest_args.append(str(test_path))
    else:
        test_dirs = []
        for test_dir_name in ["tests", "test", "src/tests"]:
            test_dir = app_path / test_dir_name
            if test_dir.exists() and test_dir.is_dir():
                test_dirs.append(test_dir_name)

        if test_dirs:
            pytest_args.extend(test_dirs)
        else:
            pytest_args.append(".")

    pytest_args.extend(["--tb=short", "--color=yes", "-o", "addopts="])

    if parallel and not watch:
        pytest_args.extend(["-n", "auto"])

    if not coverage:
        pytest_args.append("--no-cov")

    if verbose:
        pytest_args.append("-v")

    if junit_xml and not watch:
        pytest_args.append(f"--junitxml={junit_xml}")

    console.print(f"[bold green]Running tests for app in {app_path}[/bold green]")
    if test_path:
        console.print(f"[dim]Test path: {test_path}[/dim]")
    console.print(f"[dim]Command: {pytest_cmd}[/dim]")
    console.print(f"[dim]Parallel: {parallel and not watch}[/dim]")
    console.print(f"[dim]Coverage: {coverage}[/dim]")
    if watch:
        console.print("[dim]Watch mode: enabled[/dim]")

    try:
        result = subprocess.run(
            pytest_args,
            cwd=app_path,
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[red]Tests failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
        else:
            console.print("[bold green]All tests passed![/bold green]")
    except KeyboardInterrupt:
        console.print("[yellow]Tests interrupted by user[/yellow]")
        raise typer.Exit(130)
    except FileNotFoundError:
        console.print(
            f"[red]Error: {pytest_cmd} not found. "
            "Make sure pytest is installed in the app's environment.[/red]"
        )
        raise typer.Exit(1)
