import argparse
import pathlib
import sys
from typing import List

from ruamel.yaml import (
    YAML,
)

from gen_base.gen_typing import TestSuiteCreator


def make_filename_for_test(test):
    title = test["title"]
    filename = title.lower().replace(" ", "_") + ".yaml"
    return pathlib.Path(filename)


def validate_output_dir(path_str):
    path = pathlib.Path(path_str)

    if not path.exists():
        raise argparse.ArgumentTypeError("Output directory must exist")

    if not path.is_dir():
        raise argparse.ArgumentTypeError("Output path must lead to a directory")

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

    args = parser.parse_args()
    output_dir = args.output_dir
    if not args.force:
        file_mode = "x"
    else:
        file_mode = "w"

    yaml = YAML(pure=True)

    print(f"Generating tests for {generator_name}, creating {len(suite_creators)} test suite files...")
    for suite_creator in suite_creators:
        suite = suite_creator()

        filename = make_filename_for_test(suite)
        path = output_dir / filename

        try:
            with path.open(file_mode) as f:
                yaml.dump(suite, f)
        except IOError as e:
            sys.exit(f'Error when dumping test "{suite["title"]}" ({e})')

    print("done.")
