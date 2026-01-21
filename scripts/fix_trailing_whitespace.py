#!/usr/bin/env python3
"""
Fix trailing whitespace in all tracked and untracked (non-ignored) files.
"""
import subprocess


def get_files():
    """Get tracked files + untracked non-ignored files."""
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.strip().split('\n') if f]


def fix_file(filepath):
    """Fix trailing whitespace in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original = f.read()
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return

    lines = original.split('\n')
    fixed = '\n'.join(line.rstrip() for line in lines)

    if fixed != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed)


if __name__ == '__main__':
    for filepath in get_files():
        fix_file(filepath)
