#!/usr/bin/env python3
"""
Check for markdown heading level violations.

Headings should not skip levels (e.g., ## followed by #### is invalid).
"""

import re
import sys
from pathlib import Path


def check_file(file_path):
    """Check a single file for heading level violations."""
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError):
        return violations

    # Pattern to match markdown headings (must be at start of line)
    heading_pattern = r"^(#{1,6})\s+(.+)$"

    in_code_block = False
    prev_level = 0

    for line_num, line in enumerate(lines, 1):
        stripped = line.rstrip()

        # Track code blocks to skip headings inside them
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        match = re.match(heading_pattern, stripped)
        if match:
            hashes = match.group(1)
            heading_text = match.group(2)
            level = len(hashes)

            # Check for skipped levels (e.g., ## then ####)
            # First heading can be any level, subsequent ones can't skip
            if prev_level > 0 and level > prev_level + 1:
                violations.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "content": stripped,
                        "message": f"Heading level {level} skips level {prev_level + 1} (previous was level {prev_level})",
                    }
                )

            prev_level = level

    return violations


def main():
    """Main function to check all relevant files."""
    if len(sys.argv) > 1:
        # Check specific files passed as arguments
        files_to_check = sys.argv[1:]
    else:
        # Check all markdown files in the specs directory
        files_to_check = list(Path("specs").rglob("*.md"))

    all_violations = []

    for file_path in files_to_check:
        violations = check_file(file_path)
        all_violations.extend(violations)

    if all_violations:
        print(f"Found {len(all_violations)} markdown heading violations:")
        print()

        for violation in all_violations:
            print(f"File:    {violation['file']}:{violation['line']}")
            print(f"Content: {violation['content']}")
            print(f"Message: {violation['message']}")
            print()

        sys.exit(1)


if __name__ == "__main__":
    main()
