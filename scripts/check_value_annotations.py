#!/usr/bin/env python3
"""
Check for incorrect or poorly formatted (= VALUE) annotations in spec markdown.

Verifies:
1. Computed values match annotations (e.g., 2**8 actually equals 256)
2. Numbers >= 1,000 use comma formatting (e.g., 2,048 not 2048)
"""

import re
import sys
from pathlib import Path


# Pattern for markdown: `EXPR` ... (= VALUE)
MD_ANNOTATION_PATTERN = re.compile(r"`([^`]+)`[^(`]*\(=\s*([^)]+)\)")

# Pattern for YAML comments: # EXPR (= VALUE)
YAML_ANNOTATION_PATTERN = re.compile(r"^#\s*(?:\[customized\]\s*)?(.+?)\s+\(=\s*([^)]+)\)")

# Type wrappers to strip before evaluation: any Identifier(...) pattern
TYPE_WRAPPER = re.compile(r"^[A-Za-z_]\w*\((.+)\)$")

# Pure arithmetic: only digits, spaces, operators, and parens
PURE_ARITHMETIC = re.compile(r"^[\d\s\*\+\-\/\(\)]+$")

# Leading number (possibly comma-formatted) in the annotation value.
# Must start and end with a digit to avoid capturing trailing separator commas.
LEADING_NUMBER = re.compile(r"^\d[\d,]*\d|\d")


def strip_type_wrapper(expr):
    """Strip type wrappers like uint64(...), Gwei(...), etc."""
    m = TYPE_WRAPPER.match(expr.strip())
    if m:
        return m.group(1)
    return expr.strip()


def is_pure_arithmetic(expr):
    """Check if expression contains only arithmetic operations."""
    return bool(PURE_ARITHMETIC.match(expr))


def safe_eval_arithmetic(expr):
    """Safely evaluate a pure arithmetic expression."""
    try:
        result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307
        if isinstance(result, (int, float)):
            return int(result)
    except Exception:
        pass
    return None


def parse_annotated_number(value_str):
    """Extract the leading number from an annotation value string.

    Handles: "256", "16,777,216", "4096 epochs", "10485760, 10 MiB", "33024, ~5 months"
    Returns the raw integer or None if no number found.
    """
    value_str = value_str.strip()
    m = LEADING_NUMBER.match(value_str)
    if not m:
        return None, None
    raw = m.group(0)
    try:
        number = int(raw.replace(",", ""))
    except ValueError:
        return None, None
    return number, raw


def check_comma_formatting(number, raw_str):
    """Check if a number >= 1000 is properly comma-formatted.

    Returns an error message if formatting is wrong, None if correct.
    """
    if number < 1000:
        return None
    expected = f"{number:,}"
    if raw_str != expected:
        return f"Number {raw_str} should be comma-formatted as {expected}"
    return None


def check_file(file_path):
    """Check a single file for value annotation issues."""
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError):
        return violations

    is_yaml = str(file_path).endswith((".yaml", ".yml"))
    pattern = YAML_ANNOTATION_PATTERN if is_yaml else MD_ANNOTATION_PATTERN
    in_code_block = False

    for line_num, line in enumerate(lines, 1):
        stripped = line.rstrip()

        # Track code blocks to skip annotations inside them (markdown only)
        if not is_yaml and stripped.lstrip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        for match in pattern.finditer(line):
            expr = match.group(1)
            value_str = match.group(2)

            # Parse the annotated number
            number, raw_str = parse_annotated_number(value_str)
            if number is None:
                continue

            # Strip type wrapper and check if pure arithmetic
            inner_expr = strip_type_wrapper(expr)

            if is_pure_arithmetic(inner_expr) and not inner_expr.strip().isdigit():
                computed = safe_eval_arithmetic(inner_expr)
                if computed is not None and computed != number:
                    violations.append(
                        {
                            "file": file_path,
                            "line": line_num,
                            "content": stripped.strip(),
                            "message": f"Value mismatch: `{expr}` evaluates to {computed:,} but annotation says {raw_str}",
                        }
                    )

            # Check comma formatting regardless
            fmt_error = check_comma_formatting(number, raw_str)
            if fmt_error is not None:
                violations.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "content": stripped.strip(),
                        "message": fmt_error,
                    }
                )

    return violations


def main():
    """Main function to check all relevant files."""
    if len(sys.argv) > 1:
        # Check specific files passed as arguments
        files_to_check = sys.argv[1:]
    else:
        # Check all markdown files in specs and YAML files in configs/presets
        files_to_check = list(Path("specs").rglob("*.md"))
        files_to_check += list(Path("configs").rglob("*.yaml"))
        files_to_check += list(Path("presets").rglob("*.yaml"))

    all_violations = []

    for file_path in files_to_check:
        violations = check_file(file_path)
        all_violations.extend(violations)

    if all_violations:
        print(f"Found {len(all_violations)} value annotation violations:")
        print()

        for violation in all_violations:
            print(f"File:    {violation['file']}:{violation['line']}")
            print(f"Content: {violation['content']}")
            print(f"Message: {violation['message']}")
            print()

        sys.exit(1)


if __name__ == "__main__":
    main()
