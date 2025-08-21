import argparse

from tomlkit import parse, dumps
from tomlkit.container import Container

from typing import cast


def update_version(version: str) -> None:
    pyproject_path = "pyproject.toml"

    try:
        # Read the pyproject.toml file
        with open(pyproject_path) as file:
            pyproject_content = file.read()

        # Parse the TOML content
        pyproject_data = parse(pyproject_content)

        # Update the version in the "project" table
        project_table = cast(Container, pyproject_data["project"])
        project_table["version"] = version

        # Write the updated content back to the file
        with open(pyproject_path, "w") as file:
            file.write(dumps(pyproject_data))

        print(f"Version updated to {version} in pyproject.toml")

    except FileNotFoundError:
        print(f"Error: {pyproject_path} not found")
    except Exception as e:
        print(f"An error occurred: {e}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Update the version in pyproject.toml")
    parser.add_argument(
        "version", type=str, help="New version to set in pyproject.toml"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    update_version(args.version)
