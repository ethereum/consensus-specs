#!/usr/bin/env python3
"""
Standalone script to generate Ethereum consensus specs from markdown files.

This script parses markdown specification files and generates Python modules
for each fork (phase0, altair, bellatrix, capella, deneb, electra, etc.)
with different presets (minimal, mainnet).

The generated Python modules are written to the output directory and can be
imported as part of the eth2spec package.

Usage:
    python pysetup/generate_specs.py [options]

    # Generate all forks to default location
    python pysetup/generate_specs.py --all-forks

    # Generate specific fork
    python pysetup/generate_specs.py --fork phase0 --out-dir ./output

Dependencies:
    - marko: Markdown parsing
    - ruamel.yaml: YAML config/preset loading
"""

import argparse
import copy
import sys
from collections import OrderedDict
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import cast

try:
    from ruamel.yaml import YAML
except ImportError:
    print("Error: Missing required dependencies.", file=sys.stderr)
    print("Run: uv sync --all-extras", file=sys.stderr)
    sys.exit(1)

from pysetup.constants import PHASE0
from pysetup.helpers import (
    combine_spec_objects,
    dependency_order_class_objects,
    objects_to_spec,
    parse_config_vars,
)
from pysetup.md_doc_paths import get_md_doc_paths
from pysetup.md_to_spec import MarkdownToSpec
from pysetup.spec_builders import spec_builders
from pysetup.typing import BuildTarget, SpecObject  # type: ignore[attr-defined]


def get_spec(
    file_name: Path,
    preset: dict[str, str],
    config: dict[str, str | list[dict[str, str]]],
    preset_name: str,
) -> SpecObject:
    """Parse a single markdown spec file into a SpecObject."""
    return MarkdownToSpec(file_name, preset, config, preset_name).run()


@cache
def load_preset(preset_files: Sequence[Path]) -> dict[str, str]:
    """
    Loads a directory of preset files, merges the result into one preset.
    """
    preset: dict[str, str] = {}
    for fork_file in preset_files:
        yaml = YAML(typ="base")
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(f"duplicate config var(s) in preset files: {', '.join(duplicates)}")
        preset.update(fork_preset)
    assert preset != {}
    return cast(dict[str, str], parse_config_vars(preset))


@cache
def load_config(config_path: Path) -> dict[str, str | list[dict[str, str]]]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ="base")
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


def build_spec(
    fork: str,
    preset_name: str,
    source_files: Sequence[Path],
    preset_files: Sequence[Path],
    config_file: Path,
) -> str:
    """
    Build a complete spec Python module from markdown sources.

    Args:
        fork: The fork name (e.g., 'phase0', 'altair', 'bellatrix')
        preset_name: The preset name (e.g., 'minimal', 'mainnet')
        source_files: List of markdown spec files to parse
        preset_files: List of preset YAML files to load
        config_file: Path to config YAML file

    Returns:
        A complete Python module as a string
    """
    preset = load_preset(tuple(preset_files))
    config = load_config(config_file)
    all_specs = [get_spec(spec, preset, config, preset_name) for spec in source_files]

    spec_object = all_specs[0]
    for value in all_specs[1:]:
        spec_object = combine_spec_objects(spec_object, value)

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}

    # Ensure it's ordered after multiple forks
    new_objects: dict[str, str] = {}
    while OrderedDict(new_objects) != OrderedDict(class_objects):
        new_objects = copy.deepcopy(class_objects)
        dependency_order_class_objects(
            class_objects,
            spec_object.custom_types | spec_object.preset_dep_custom_types,
        )

    return objects_to_spec(preset_name, spec_object, fork, class_objects)


def parse_build_targets(targets_str: str) -> list[BuildTarget]:
    """
    Parse build target strings in format: name:preset_dir:config_file

    Example:
        minimal:presets/minimal:configs/minimal.yaml
        mainnet:presets/mainnet:configs/mainnet.yaml
    """
    build_targets = []
    for target in targets_str.strip().split():
        target = target.strip()
        if not target:
            continue

        data = target.split(":")
        if len(data) != 3:
            raise ValueError(
                f"invalid target, expected 'name:preset_dir:config_file' format, but got: {target}"
            )

        name, preset_dir_path, config_path = data

        # Validate preset name
        if not name.isalnum():
            raise ValueError(f"invalid target name (must be alphanumeric): {name!r}")

        # Validate preset directory
        preset_dir = Path(preset_dir_path)
        if not preset_dir.exists():
            raise FileNotFoundError(f"Preset directory does not exist: {preset_dir}")

        # Collect all preset files from the directory
        preset_paths = sorted(preset_dir.glob("*.yaml"))
        if not preset_paths:
            raise FileNotFoundError(f"No YAML files found in preset directory: {preset_dir}")

        # Validate config file
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file does not exist: {config_file}")

        build_targets.append(BuildTarget(name, preset_paths, config_file))

    return build_targets


def generate_fork_specs(
    fork: str,
    out_dir: Path,
    build_targets: list[BuildTarget],
    source_files: list[Path] | None = None,
    verbose: bool = False,
) -> None:
    """
    Generate spec Python modules for a specific fork.

    Args:
        fork: The fork name (e.g., 'phase0', 'altair')
        out_dir: Output directory where spec modules will be written
        build_targets: List of BuildTarget (preset configurations)
        source_files: List of markdown source files (auto-detected if None)
        verbose: Enable verbose output
    """
    if fork not in spec_builders:
        raise ValueError(f"Unknown fork: {fork}. Available: {list(spec_builders.keys())}")

    # Auto-detect source files if not provided
    if source_files is None:
        md_doc_paths = get_md_doc_paths(fork)
        if not md_doc_paths:
            raise ValueError(f"No markdown files found for fork: {fork}")
        source_files = [Path(p) for p in md_doc_paths.split()]

    # Validate all source files exist
    for source_file in source_files:
        if not source_file.exists():
            raise FileNotFoundError(f"Spec markdown file does not exist: {source_file}")

    # Create output directory
    out_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"Generating specs for fork: {fork}")
        print(f"  Source files: {len(source_files)}")
        print(f"  Build targets: {[t.name for t in build_targets]}")
        print(f"  Output directory: {out_dir}")

    # Generate spec for each build target (minimal, mainnet, etc.)
    for target in build_targets:
        if verbose:
            print(f"  Building target: {target.name}")

        spec_str = build_spec(
            spec_builders[fork].fork,
            target.name,
            source_files,
            target.preset_paths,
            target.config_path,
        )

        output_file = out_dir / f"{target.name}.py"
        output_file.write_text(spec_str)

        if verbose:
            print(f"    Wrote: {output_file} ({len(spec_str):,} bytes)")

    # Create __init__.py that imports mainnet as default
    init_file = out_dir / "__init__.py"
    init_file.write_text("from . import mainnet as spec  # noqa:F401\n")

    if verbose:
        print(f"  Wrote: {init_file}")


def main() -> int:
    """Main entry point for the spec generation script."""
    parser = argparse.ArgumentParser(
        description="Generate Ethereum consensus specs from markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all forks to default location (tests/core/pyspec/eth2spec/)
  python pysetup/generate_specs.py --all-forks

  # Generate specific fork
  python pysetup/generate_specs.py --fork phase0

  # Generate to custom directory
  python pysetup/generate_specs.py --fork deneb --out-dir ./build/specs

  # Use custom build targets
  python pysetup/generate_specs.py --fork phase0 \\
      --build-targets "minimal:presets/minimal:configs/minimal.yaml"
        """,
    )

    parser.add_argument(
        "--fork",
        type=str,
        default=None,
        help=f"Spec fork to generate (default: {PHASE0}). Available: {', '.join(spec_builders.keys())}",
    )

    parser.add_argument(
        "--all-forks",
        action="store_true",
        help="Generate specs for all available forks",
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: tests/core/pyspec/eth2spec/<fork>)",
    )

    parser.add_argument(
        "--build-targets",
        type=str,
        default="minimal:presets/minimal:configs/minimal.yaml mainnet:presets/mainnet:configs/mainnet.yaml",
        help="Space-separated build targets in format 'name:preset_dir:config_file'",
    )

    parser.add_argument(
        "--source-files",
        type=str,
        default=None,
        help="Space-separated list of markdown source files (auto-detected if not specified)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    try:
        # Parse build targets
        build_targets = parse_build_targets(args.build_targets)

        # Parse source files if provided
        source_files = None
        if args.source_files:
            source_files = [Path(p) for p in args.source_files.split()]

        # Determine which forks to generate
        if args.all_forks:
            forks = list(spec_builders.keys())
        elif args.fork:
            forks = [args.fork]
        else:
            forks = [PHASE0]

        # Generate specs for each fork
        for fork in forks:
            # Determine output directory
            if args.out_dir:
                out_dir = args.out_dir
            else:
                out_dir = Path("tests/core/pyspec/eth2spec") / fork

            generate_fork_specs(
                fork=fork,
                out_dir=out_dir,
                build_targets=build_targets,
                source_files=source_files,
                verbose=args.verbose,
            )

        if args.verbose:
            print(f"\nSuccessfully generated {len(forks)} fork(s)")

        return 0

    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
