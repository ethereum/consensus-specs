import argparse
import pathlib
import sys

from ruamel.yaml import (
    YAML,
)

from uint_test_generators import (
    generate_uint_bounds_test,
    generate_uint_random_test,
    generate_uint_wrong_length_test,
)

test_generators = [
    generate_uint_random_test,
    generate_uint_wrong_length_test,
    generate_uint_bounds_test,
]


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


parser = argparse.ArgumentParser(
    prog="gen-ssz-tests",
    description="Generate YAML test files for SSZ and tree hashing",
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


if __name__ == "__main__":
    args = parser.parse_args()
    output_dir = args.output_dir
    if not args.force:
        file_mode = "x"
    else:
        file_mode = "w"

    yaml = YAML(pure=True)

    print(f"generating {len(test_generators)} test files...")
    for test_generator in test_generators:
        test = test_generator()

        filename = make_filename_for_test(test)
        path = output_dir / filename

        try:
            with path.open(file_mode) as f:
                yaml.dump(test, f)
        except IOError as e:
            sys.exit(f'Error when dumping test "{test["title"]}" ({e})')

    print("done.")
