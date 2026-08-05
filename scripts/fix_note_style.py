#!/usr/bin/env python3
"""
Enforce a consistent note prefix style in markdown files.

The canonical style is `*Note*:` (italicized "Note" followed by a colon).
This script rewrites the common variants in place:

    *Note:*       -> *Note*:
    **Note**:     -> *Note*:
    **Note:**     -> *Note*:
    NOTE:         -> *Note*:
    Note:         -> *Note*:
    *Note* <text> -> *Note*: <text>

Only the start of a line (after optional whitespace and `>` blockquote
markers) is rewritten. Lines inside fenced code blocks are left alone.
"""

import re
import subprocess

LINE_START = r"^([ \t]*(?:>[ \t]*)*)"

# Order matters: longer / more specific patterns come first so we don't
# partially match a longer variant with a shorter pattern. Matching is
# case-insensitive so variants like `NOTE:` or `NoTe:` are also caught;
# the replacement always normalizes to the canonical `*Note*:`.
PATTERNS = [
    (re.compile(LINE_START + r"\*\*Note:\*\*", re.IGNORECASE), r"\1*Note*:"),
    (re.compile(LINE_START + r"\*\*Note\*\*:", re.IGNORECASE), r"\1*Note*:"),
    (re.compile(LINE_START + r"\*Note:\*", re.IGNORECASE), r"\1*Note*:"),
    (re.compile(LINE_START + r"\*Note\*(?=\s+)(?!:)", re.IGNORECASE), r"\1*Note*:"),
    (re.compile(LINE_START + r"Note:", re.IGNORECASE), r"\1*Note*:"),
]


def get_markdown_files():
    """Get tracked + untracked non-ignored markdown files."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def fix_text(text):
    """Return (fixed_text, num_changes) for one file's contents."""
    out_lines = []
    changes = 0
    in_fence = False

    for line in text.split("\n"):
        # Toggle fenced code block on lines starting (after whitespace) with ```.
        if re.match(r"^[ \t]*```", line):
            in_fence = not in_fence
            out_lines.append(line)
            continue

        if in_fence:
            out_lines.append(line)
            continue

        new_line = line
        for pattern, repl in PATTERNS:
            new_line, n = pattern.subn(repl, new_line, count=1)
            if n:
                changes += n
                break  # one replacement per line is enough

        out_lines.append(new_line)

    return "\n".join(out_lines), changes


def main():
    total_changes = 0
    changed_files = []

    for path in get_markdown_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                original = f.read()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue

        fixed, changes = fix_text(original)
        if changes and fixed != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(fixed)
            total_changes += changes
            changed_files.append((path, changes))

    if changed_files:
        for path, changes in changed_files:
            print(f"{path}: fixed {changes} note prefix(es)")
        print(f"Fixed {total_changes} note prefix(es) in {len(changed_files)} file(s).")


if __name__ == "__main__":
    main()
