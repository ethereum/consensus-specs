#!/usr/bin/env python3
"""
Generate index.md files for specification directories to enable directory browsing in mkdocs.

This script is used by the mkdocs-gen-files plugin to create virtual index pages
that list all files in each specification directory, providing a GitHub-like
directory browsing experience on the mkdocs documentation site.
"""

import os
import mkdocs_gen_files


def format_filename_as_title(filename: str) -> str:
    """Convert a filename to a human-readable title."""
    name = filename[-3] if filename.endswith(".md") else filename

    replacements = {
        "api": "API",
        "bls": "BLS",
        "das": "DAS",
        "p2p": "P2P",
        "ssz": "SSZ",
    }

    name = name.replace("-", " ").replace("_", " ")

    words = name.split()
    formatted_words = []
    for word in words:
        lower_word = word.lower()
        if lower_word in replacements:
            formatted_words.append(replacements[lower_word])
        else:
            formatted_words.append(word.title())

    return " ".join(formatted_words)


def generate_spec_index(dir_path: str, level: int = 1) -> str:
    """Generate index content for a specification directory."""
    files = []
    subdirs = []

    if os.path.exists(dir_path):
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                subdirs.append(item)
            elif item.endswith(".md") and item != "index.md":
                files.append(item)

    content = ""

    if level == 1:
        content = "# Index\n\n"
        if files:
            content += "## Core\n\n"

    for file in files:
        name = format_filename_as_title(file)
        content += f"- [{name}](./{file})\n"

    for subdir in subdirs:
        formatted_name = format_filename_as_title(subdir)
        heading_level = "#" * (level + 1)
        content += f"\n{heading_level} {formatted_name}\n\n"
        subdir_path = os.path.join(dir_path, subdir)
        subdir_content = generate_spec_index(subdir_path, level + 1)
        if subdir_content.strip():
            content += subdir_content
        else:
            content += f"*No files in {subdir}/*\n"

    if not files and not subdirs and level == 1:
        content += "*No specification files found in this directory.*\n"

    return content


print("Generating specification index pages...")

spec_forks = []
if os.path.exists("specs"):
    for item in sorted(os.listdir("specs")):
        item_path = os.path.join("specs", item)
        if os.path.isdir(item_path) and item not in {"_deprecated", "_features"}:
            spec_forks.append(item)

for fork in spec_forks:
    spec_path = f"specs/{fork}"
    print(f"  - Generating index for {spec_path}")
    with mkdocs_gen_files.open(f"{spec_path}/index.md", "w") as f:
        f.write(generate_spec_index(spec_path))
