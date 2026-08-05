#!/usr/bin/env python3
"""
Generate index.md files for specification directories to enable directory browsing.

Each specification directory gets an index page listing the documents it contains,
providing a GitHub-like directory browsing experience on the documentation site.
The pages are written directly into the docs directory, which is a copy of the
specification sources assembled by the `_copy_docs` make target.
"""

import os
import sys

REPLACEMENTS = {
    "api": "API",
    "bls": "BLS",
    "das": "DAS",
    "p2p": "P2P",
    "ssz": "SSZ",
}


def format_filename_as_title(filename: str) -> str:
    """Convert a filename to a human-readable title."""
    name = filename[:-3] if filename.endswith(".md") else filename

    name = name.replace("-", " ").replace("_", " ")

    formatted_words = []
    for word in name.split():
        lower_word = word.lower()
        if lower_word in REPLACEMENTS:
            formatted_words.append(REPLACEMENTS[lower_word])
        else:
            formatted_words.append(word.title())

    return " ".join(formatted_words)


def list_dir(dir_path: str) -> tuple[list[str], list[str]]:
    """Return the markdown files and subdirectories of a directory."""
    files = []
    subdirs = []

    if os.path.exists(dir_path):
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                subdirs.append(item)
            elif item.endswith(".md") and item != "index.md":
                files.append(item)

    return files, subdirs


def generate_spec_index(dir_path: str, level: int = 1, prefix: str = "") -> str:
    """Generate index content for a specification directory.

    The prefix is the path of dir_path relative to the directory that the index
    page is written to, so that links to nested documents resolve correctly.
    """
    files, subdirs = list_dir(dir_path)

    content = ""

    if level == 1:
        content = "# Index\n\n"
        if files:
            content += "## Core\n\n"

    for file in files:
        name = format_filename_as_title(file)
        content += f"- [{name}](./{prefix}{file})\n"

    for subdir in subdirs:
        formatted_name = format_filename_as_title(subdir)
        heading_level = "#" * (level + 1)
        content += f"\n{heading_level} {formatted_name}\n\n"
        subdir_path = os.path.join(dir_path, subdir)
        subdir_content = generate_spec_index(subdir_path, level + 1, f"{prefix}{subdir}/")
        if subdir_content.strip():
            content += subdir_content
        else:
            content += f"*No files in {subdir}/*\n"

    if not files and not subdirs and level == 1:
        content += "*No specification files found in this directory.*\n"

    return content


def fork_nav_order(fork: str) -> tuple[int, str]:
    """Sort phase0 first and the features directory last, alphabetical in between."""
    if fork == "phase0":
        return (0, fork)
    if fork == "_features":
        return (2, fork)
    return (1, fork)


def toml_string(value: str) -> str:
    """Quote a value as a basic TOML string."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def nav_entries(dir_path: str, url_prefix: str) -> list[str]:
    """Return the navigation entries of a directory as inline TOML tables.

    Documents are titled after their filename rather than their heading, which
    is far shorter, as every specification repeats its fork in the heading.
    """
    files, subdirs = list_dir(dir_path)

    entries = []
    for file in files:
        title = toml_string(format_filename_as_title(file))
        entries.append(f"{{ {title} = {toml_string(url_prefix + file)} }}")

    for subdir in subdirs:
        title = toml_string(format_filename_as_title(subdir))
        children = nav_entries(os.path.join(dir_path, subdir), f"{url_prefix}{subdir}/")
        entries.append(f"{{ {title} = [{', '.join(children)}] }}")

    return entries


def generate_nav(specs_dir: str, url_prefix: str) -> str:
    """Generate the navigation, which lists one section per fork.

    Zensical builds a navigation from the directory tree when none is
    configured, but it sorts the forks alphabetically and titles the documents
    after their heading. The navigation is generated here instead, so that the
    forks stay in chronological order and the titles stay short. Neither can be
    expressed in the configuration file, as it is not aware of the forks.
    """
    _, fork_dirs = list_dir(specs_dir)

    sections = []
    for fork in sorted(fork_dirs, key=fork_nav_order):
        title = toml_string(format_filename_as_title(fork))
        index = toml_string(f"{url_prefix}{fork}/index.md")
        entries = nav_entries(os.path.join(specs_dir, fork), f"{url_prefix}{fork}/")

        lines = ["[[project.nav]]", f"{title} = [", f"  {index},"]
        lines += [f"  {entry}," for entry in entries]
        lines.append("]")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def main(docs_dir: str, config_in: str, config_out: str) -> None:
    """Write the index pages of the specifications and the site configuration."""
    print("Generating specification index pages...")

    specs_dir = os.path.join(docs_dir, "specs")
    if not os.path.isdir(specs_dir):
        print(f"error: specifications directory does not exist: {specs_dir}")
        sys.exit(1)

    _, fork_dirs = list_dir(specs_dir)
    for fork in fork_dirs:
        fork_path = os.path.join(specs_dir, fork)
        index_path = os.path.join(fork_path, "index.md")
        print(f"  - Generating {index_path}")
        with open(index_path, "w") as f:
            f.write(generate_spec_index(fork_path))

    print(f"  - Generating {config_out}")
    with open(config_in) as f:
        config = f.read().rstrip("\n")

    nav = generate_nav(specs_dir, "specs/")
    with open(config_out, "w") as f:
        f.write(f"{config}\n\n{nav}\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
