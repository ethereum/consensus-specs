#!/usr/bin/env python3
"""
Check if the current Python version meets requirements from pyproject.toml
"""

import re
import sys
from pathlib import Path


def main():
    """Check Python version against pyproject.toml requirements."""
    # Read pyproject.toml from project root
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        sys.exit(1)

    content = pyproject_path.read_text()

    # Extract requires-python line
    match = re.search(r'requires-python\s*=\s*"([^"]*)"', content)
    if not match:
        print("Error: requires-python not found in pyproject.toml")
        sys.exit(1)

    required_version = match.group(1)

    # Parse version requirements (e.g., ">=3.10,<4.0")
    min_match = re.search(r">=([0-9.]+)", required_version)
    max_match = re.search(r"<([0-9.]+)", required_version)

    if not min_match:
        print(f"Error: Could not parse minimum version from: {required_version}")
        sys.exit(1)

    min_version = tuple(map(int, min_match.group(1).split(".")))
    current_version = sys.version_info[:2]

    print(f"Required: {required_version}, Current: {current_version[0]}.{current_version[1]}")

    # Check minimum version
    if current_version < min_version:
        print(
            f"Error: Python {current_version[0]}.{current_version[1]} is not supported. Required: {required_version}"
        )
        sys.exit(1)

    # Check maximum version if specified
    if max_match:
        max_version = tuple(map(int, max_match.group(1).split(".")))
        if current_version >= max_version:
            print(
                f"Error: Python {current_version[0]}.{current_version[1]} is not supported. Required: {required_version}"
            )
            sys.exit(1)

    print(f"✓ Python {current_version[0]}.{current_version[1]} meets requirements")


if __name__ == "__main__":
    main()
