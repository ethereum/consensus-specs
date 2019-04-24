import argparse
from pathlib import Path
import sys
from typing import List

from ruamel.yaml import (
    YAML,
)

from gen_base.gen_typing import TestSuiteCreator


def validate_output_dir(path_str):
    path = Path(path_str)

    if not path.exists():
        raise argparse.ArgumentTypeError("Output directory must exist")

    if not path.is_dir():
        raise argparse.ArgumentTypeError("Output path must lead to a directory")

    return path


def validate_configs_dir(path_str):
    path = Path(path_str)

    if not path.exists():
        raise argparse.ArgumentTypeError("Configs directory must exist")

    if not path.is_dir():
        raise argparse.ArgumentTypeError("Config path must lead to a directory")

    if not Path(path, "constant_presets").exists():
        raise argparse.ArgumentTypeError("Constant Presets directory must exist")

    if not Path(path, "constant_presets").is_dir():
        raise argparse.ArgumentTypeError("Constant Presets path must lead to a directory")

    if not Path(path, "fork_timelines").exists():
        raise argparse.ArgumentTypeError("Fork Timelines directory must exist")

    if not Path(path, "fork_timelines").is_dir():
        raise argparse.ArgumentTypeError("Fork Timelines path must lead to a directory")

    return path


def run_generator(generator_name, suite_creators: List[TestSuiteCreator]):
    """
    Implementation for a general test generator.
    :param generator_name: The name of the generator. (lowercase snake_case)
    :param suite_creators: A list of suite creators, each of these builds a list of test cases.
    :return:
    """

    parser = argparse.ArgumentParser(
        prog="gen-" + generator_name,
        description=f"Generate YAML test suite files for {generator_name}",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        required=True,
        type=validate_output_dir,
        help="directory into which the generated YAML files will be dumped"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="if set overwrite test files if they exist",
    )
    parser.add_argument(
        "-c",
        "--configs-path",
        dest="configs_path",
        required=True,
        type=validate_configs_dir,
        help="specify the path of the configs directory (containing constants_presets and fork_timelines)",
    )

    args = parser.parse_args()
    output_dir = args.output_dir
    if not args.force:
        file_mode = "x"
    else:
        file_mode = "w"

    yaml = YAML(pure=True)
    yaml.default_flow_style = None

    print(f"Generating tests for {generator_name}, creating {len(suite_creators)} test suite files...")
    print(f"Reading config presets and fork timelines from {args.configs_path}")
    for suite_creator in suite_creators:
        (output_name, handler, suite) = suite_creator(args.configs_path)

        handler_output_dir = Path(output_dir) / Path(handler)
        try:
            if not handler_output_dir.exists():
                handler_output_dir.mkdir()
        except FileNotFoundError as e:
            sys.exit(f'Error when creating handler dir {handler} for test "{suite["title"]}" ({e})')

        out_path = handler_output_dir / Path(output_name + '.yaml')

        try:
            with out_path.open(file_mode) as f:
                yaml.dump(suite, f)
        except IOError as e:
            sys.exit(f'Error when dumping test "{suite["title"]}" ({e})')

    print("done.")
