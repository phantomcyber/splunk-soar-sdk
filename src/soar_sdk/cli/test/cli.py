from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

test = typer.Typer(
    help="Run unit and integration tests",
)

console = Console()


@test.command()
def unit(
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
            help="Path to specific test file or directory",
        ),
    ] = None,
    junit_xml: Annotated[
        Path | None,
        typer.Option(
            "--junit-xml",
            help="Path to save JUnit XML test results",
        ),
    ] = None,
) -> None:
    """Run unit tests.

    This command runs the unit test suite, excluding integration tests.
    By default, tests run in parallel for faster execution.

    Examples:
        # Run all unit tests in parallel
        soarapps test unit

        # Run unit tests with coverage
        soarapps test unit --coverage

        # Run specific test file
        soarapps test unit -t tests/test_decorators.py

        # Run without parallelism
        soarapps test unit --no-parallel
    """
    pytest_args = [
        sys.executable,
        "-m",
        "pytest",
    ]

    if test_path:
        pytest_args.append(str(test_path))

    pytest_args.extend(
        [
            "-m",
            "not integration",
            "--tb=short",
            "--color=yes",
            "-o",
            "addopts=",
        ]
    )

    if parallel:
        pytest_args.extend(["-n", "auto"])

    if not coverage:
        pytest_args.append("--no-cov")

    if verbose:
        pytest_args.append("-v")

    if junit_xml:
        pytest_args.append(f"--junitxml={junit_xml}")

    console.print("[bold green]Running unit tests[/bold green]")
    if test_path:
        console.print(f"[dim]Test path: {test_path}[/dim]")
    console.print(f"[dim]Parallel: {parallel}[/dim]")
    console.print(f"[dim]Coverage: {coverage}[/dim]")

    try:
        result = subprocess.run(  # noqa: S603
            pytest_args,
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[red]Tests failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
        else:
            console.print("[bold green]All tests passed![/bold green]")
    except KeyboardInterrupt:
        console.print("[yellow]Tests interrupted by user[/yellow]")
        raise typer.Exit(130) from None


@test.command()
def integration(
    instance_ip: Annotated[
        str,
        typer.Argument(
            help="SOAR instance IP address or hostname",
        ),
    ],
    username: Annotated[
        str | None,
        typer.Option(
            "--username",
            "-u",
            help="SOAR instance username",
            envvar="PHANTOM_USERNAME",
        ),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            "-p",
            help="SOAR instance password",
            envvar="PHANTOM_PASSWORD",
        ),
    ] = None,
    retries: Annotated[
        int,
        typer.Option(
            "--retries",
            "-r",
            help="Number of test retries on failure",
        ),
    ] = 2,
    automation_broker: Annotated[
        str | None,
        typer.Option(
            "--automation-broker",
            "-ab",
            help="Automation broker name for on-prem tests",
            envvar="AUTOMATION_BROKER_NAME",
        ),
    ] = None,
    force_automation_broker: Annotated[
        bool,
        typer.Option(
            "--force-automation-broker",
            help="Force use of automation broker for all tests",
            envvar="FORCE_AUTOMATION_BROKER",
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
            help="Path to specific test file or directory",
        ),
    ] = None,
    junit_xml: Annotated[
        Path | None,
        typer.Option(
            "--junit-xml",
            help="Path to save JUnit XML test results",
        ),
    ] = None,
) -> None:
    """Run integration tests against a SOAR instance.

    This command runs the integration test suite against a specified SOAR instance.
    Tests run similar to the GitHub CI workflow.

    Examples:
        # Run integration tests against a specific instance
        soarapps test integration 10.1.19.88 -u admin -p password

        # Run tests with automation broker
        soarapps test integration 10.1.19.88 --automation-broker my-broker

        # Run specific test file
        soarapps test integration 10.1.19.88 -t tests/integration/test_example_app.py

        # Save test results to file
        soarapps test integration 10.1.19.88 --junit-xml results.xml
    """
    if not username:
        console.print(
            "[red]Error: Username is required (use -u or PHANTOM_USERNAME env var)[/red]"
        )
        raise typer.Exit(1)

    if not password:
        console.print(
            "[red]Error: Password is required (use -p or PHANTOM_PASSWORD env var)[/red]"
        )
        raise typer.Exit(1)

    phantom_url = f"https://{instance_ip}"

    env = os.environ.copy()
    env["PHANTOM_URL"] = phantom_url
    env["PHANTOM_USERNAME"] = username
    env["PHANTOM_PASSWORD"] = password

    if automation_broker:
        env["AUTOMATION_BROKER_NAME"] = automation_broker

    if force_automation_broker:
        env["FORCE_AUTOMATION_BROKER"] = "true"

    test_dir = Path("tests/integration/")
    if test_path:
        test_dir = test_path

    pytest_args = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        "-m",
        "integration",
        "--no-cov",
        "--tb=short",
        "--color=yes",
        "-o",
        "addopts=",
        f"--reruns={retries}",
    ]

    if verbose:
        pytest_args.append("-v")

    if junit_xml:
        pytest_args.append(f"--junitxml={junit_xml}")

    console.print(
        f"[bold green]Running integration tests against {instance_ip}[/bold green]"
    )
    console.print(f"[dim]Test directory: {test_dir}[/dim]")
    console.print(f"[dim]Retries: {retries}[/dim]")
    if automation_broker:
        console.print(f"[dim]Automation broker: {automation_broker}[/dim]")

    try:
        result = subprocess.run(  # noqa: S603
            pytest_args,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[red]Tests failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
        else:
            console.print("[bold green]All tests passed![/bold green]")
    except KeyboardInterrupt:
        console.print("[yellow]Tests interrupted by user[/yellow]")
        raise typer.Exit(130) from None
