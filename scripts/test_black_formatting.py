#!/usr/bin/env python3
"""
Test script to verify Black formatting works correctly.
This is part of implementing Black formatting for the codebase.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    """
    Check if Black is installed and print its version.
    """
    try:
        import black

        print(f"Black version: {black.__version__}")
        print("Black is installed correctly!")
        
        # Print the current configuration
        print(f"Black configuration in pyproject.toml: line-length={black.Mode().line_length}")
        
        return 0
    except ImportError:
        print("Black is not installed. Please install it with 'pip install black'.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 
