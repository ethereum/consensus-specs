#!/usr/bin/env python3
"""
Generate index.md files for specification directories to enable directory browsing in MkDocs.

This script is used by the mkdocs-gen-files plugin to create virtual index pages
that list all files in each specification directory, providing a GitHub-like
directory browsing experience on the MkDocs documentation site.
"""

import os
from pathlib import Path
import mkdocs_gen_files


def format_filename_as_title(filename: str) -> str:
    """Convert a filename to a human-readable title."""
    # Remove .md extension
    name = filename[:-3] if filename.endswith('.md') else filename

    # Special case handling for common abbreviations
    replacements = {
        'p2p': 'P2P',
        'api': 'API',
        'ssz': 'SSZ',
        'bls': 'BLS',
    }

    # Replace hyphens and underscores with spaces
    name = name.replace('-', ' ').replace('_', ' ')

    # Title case
    words = name.split()
    formatted_words = []
    for word in words:
        lower_word = word.lower()
        if lower_word in replacements:
            formatted_words.append(replacements[lower_word])
        else:
            formatted_words.append(word.title())

    return ' '.join(formatted_words)


def generate_spec_index(dir_path: str, fork_name: str) -> str:
    """Generate index content for a specification directory."""
    files = []
    subdirs = []

    # Check if directory exists
    if os.path.exists(dir_path):
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                subdirs.append(item)
            elif item.endswith('.md') and item != 'index.md':
                files.append(item)

    # Generate content
    content = f"# {fork_name.title()} Specifications\n\n"

    # Add description based on fork
    descriptions = {
        'phase0': "The initial Ethereum proof-of-stake specifications, defining the core beacon chain functionality.",
        'altair': "The first beacon chain upgrade, introducing sync committees and other improvements.",
        'bellatrix': "The merge upgrade, connecting the beacon chain with the execution layer.",
        'capella': "Enables withdrawals of staked ETH from the beacon chain.",
        'deneb': "Introduces proto-danksharding (EIP-4844) for improved data availability.",
        'electra': "Latest improvements to the consensus layer.",
        'fulu': "In-development specifications for future upgrades.",
        'gloas': "Builder API specifications for proposer-builder separation."
    }

    if fork_name.lower() in descriptions:
        content += f"{descriptions[fork_name.lower()]}\n\n"

    # List subdirectories first if any
    if subdirs:
        content += "## Subdirectories\n\n"
        for subdir in subdirs:
            formatted_name = format_filename_as_title(subdir)
            content += f"- [{formatted_name}](./{subdir}/)\n"
        content += "\n"

    # List specification files
    if files:
        content += "## Specification Documents\n\n"

        # Group files by category for better organization
        core_files = []
        other_files = []

        for file in files:
            if file in ['beacon-chain.md', 'fork.md', 'validator.md']:
                core_files.append(file)
            else:
                other_files.append(file)

        if core_files:
            content += "### Core Specifications\n\n"
            for file in core_files:
                name = format_filename_as_title(file)
                desc = get_file_description(file)
                content += f"- [{name}](./{file})"
                if desc:
                    content += f" - {desc}"
                content += "\n"
            content += "\n"

        if other_files:
            content += "### Additional Specifications\n\n"
            for file in other_files:
                name = format_filename_as_title(file)
                desc = get_file_description(file)
                content += f"- [{name}](./{file})"
                if desc:
                    content += f" - {desc}"
                content += "\n"

    if not files and not subdirs:
        content += "*No specification files found in this directory.*\n"

    return content


def get_file_description(filename: str) -> str:
    """Return a brief description for common specification files."""
    descriptions = {
        'beacon-chain.md': 'Core beacon chain state transition specifications',
        'fork.md': 'Fork transition logic and upgrade process',
        'validator.md': 'Validator duties and responsibilities',
        'p2p-interface.md': 'Peer-to-peer networking protocol',
        'fork-choice.md': 'Fork choice algorithm for chain selection',
        'deposit-contract.md': 'Ethereum deposit contract interface',
        'weak-subjectivity.md': 'Weak subjectivity period calculations',
        'sync-protocol.md': 'Light client sync protocol',
        'full-node.md': 'Full node requirements and behavior',
        'light-client.md': 'Light client specifications',
        'bls.md': 'BLS signature scheme specifications',
    }
    return descriptions.get(filename, '')




# The script executes directly when loaded by mkdocs-gen-files plugin
print("[gen_spec_indices.py] Generating specification index pages...")

# List of all specification forks
spec_forks = ['phase0', 'altair', 'bellatrix', 'capella', 'deneb', 'electra', 'fulu', 'gloas']

# Generate index.md for each specs directory
for fork in spec_forks:
    spec_path = f'specs/{fork}'
    if os.path.exists(spec_path):
        print(f"  - Generating index for {spec_path}")
        with mkdocs_gen_files.open(f"{spec_path}/index.md", "w") as f:
            f.write(generate_spec_index(spec_path, fork))

# Also generate for specs/_features directory
features_path = 'specs/_features'
if os.path.exists(features_path):
    # List all feature directories
    for feature in os.listdir(features_path):
        feature_path = os.path.join(features_path, feature)
        if os.path.isdir(feature_path):
            print(f"  - Generating index for {feature_path}")
            with mkdocs_gen_files.open(f"{feature_path}/index.md", "w") as f:
                f.write(generate_spec_index(feature_path, f"Feature: {feature}"))

# Note: Test directories are not included in MkDocs documentation
# They contain Python test files, not documentation
# Links to tests in README.md will continue to work on GitHub only

print("[gen_spec_indices.py] Index generation complete!")