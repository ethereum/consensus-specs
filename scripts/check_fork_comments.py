#!/usr/bin/env python3
"""
Check for fork comments inconsistencies.
"""

import re
import sys
from pathlib import Path


def check_file(file_path):
    """Check a single file for fork comments not on standalone lines."""
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError):
        return violations

    # Pattern to match fork comments (including invalid ones)
    # Single word followed by "in" followed by a fork name
    fork_comment_pattern = r"\[(\w+)\s+in\s+(\w[\w:_-]*)\]"

    for line_num, line in enumerate(lines, 1):
        # Skip markdown link lines (lines starting with - [ or * [)
        stripped = line.strip()
        if stripped.startswith("- [") or stripped.startswith("* [") or stripped.startswith("+ ["):
            continue

        matches = re.finditer(fork_comment_pattern, line)
        for match in matches:
            action = match.group(1)
            fork_ref = match.group(2)

            # Check if action is valid (only "New" or "Modified" allowed)
            if action not in ["New", "Modified"]:
                violations.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "content": line.strip(),
                        "comment": match.group(),
                        "error_type": "invalid_action",
                        "message": f"Invalid action '{action}' - only 'New' or 'Modified' are allowed",
                    }
                )
                continue

            # Check for dashes in EIP references
            if "EIP-" in fork_ref:
                violations.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "content": line.strip(),
                        "comment": match.group(),
                        "error_type": "dash_in_eip",
                        "message": "EIPs should not contain dashes",
                    }
                )
                continue

            # Check if the fork comment is within a Python-style comment
            comment_start = match.start()
            comment_end = match.end()

            # Find if there's a # before the fork comment on this line
            hash_pos = line.rfind("#", 0, comment_start)

            if hash_pos != -1:
                # This fork comment is after a #, so it's in a Python comment
                # Check if there's any non-whitespace content before the #
                content_before_hash = line[:hash_pos].strip()
                if content_before_hash:
                    # There's code before the comment, this is an inline comment
                    violations.append(
                        {
                            "file": file_path,
                            "line": line_num,
                            "content": line.strip(),
                            "comment": match.group(),
                            "error_type": "inline_comment",
                            "message": f"Fork comment '{match.group()}' should be on its own line",
                        }
                    )
                    continue

                # Check if there's any non-whitespace content after the fork comment
                content_after_comment = line[comment_end:].strip()
                if content_after_comment:
                    violations.append(
                        {
                            "file": file_path,
                            "line": line_num,
                            "content": line.strip(),
                            "comment": match.group(),
                            "error_type": "text_after_comment",
                            "message": f"Text after fork comment should be on a separate line",
                        }
                    )

    return violations


def main():
    """Main function to check all relevant files."""
    if len(sys.argv) > 1:
        # Check specific files passed as arguments
        files_to_check = sys.argv[1:]
    else:
        # Check all markdown and yaml files in the repository
        files_to_check = []
        for ext in ["*.md", "*.yaml", "*.yml"]:
            files_to_check.extend(Path(".").rglob(ext))

    all_violations = []

    for file_path in files_to_check:
        violations = check_file(file_path)
        all_violations.extend(violations)

    if all_violations:
        print(f"Found {len(all_violations)} fork comment violations:")
        print()

        for violation in all_violations:
            print(f"File:    {violation['file']}:{violation['line']}")
            print(f"Content: {violation['content']}")
            print(f"Message: {violation['message']}")
            print()

        sys.exit(1)


if __name__ == "__main__":
    main()
