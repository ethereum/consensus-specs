import argparse
from pathlib import Path
import sys
from typing import List

from ruamel.yaml import (
    YAML,
)

from gen_base.gen_typing import TestProvider


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


def run_generator(generator_name, test_providers: Iterable[TestProvider]):
    """
    Implementation for a general test generator.
    :param generator_name: The name of the generator. (lowercase snake_case)
    :param test_providers: A list of test provider,
            each of these returns a callable that returns an iterable of test cases.
            The call to get the iterable may set global configuration,
            and the iterable should not be resumed after a pause with a change of that configuration.
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

    print(f"Generating tests into {output_dir}...")
    print(f"Reading config presets and fork timelines from {args.configs_path}")

    for tprov in test_providers:
        # loads configuration etc.
        config_name = tprov.prepare(args.configs_path)
        for test_case in tprov.make_cases():
                case_dir = Path(output_dir) / Path(config_name) / Path(test_case.fork_name) \
                           / Path(test_case.runner_name) / Path(test_case.handler_name) \
                           / Path(test_case.suite_name) / Path(test_case.case_name)
                print(f'Generating test: {case_dir}')

                case_dir.mkdir(parents=True, exist_ok=True)

                try:
                    for case_part in test_case.case_fn():
                        if case_part.out_kind == "data" or case_part.out_kind == "ssz":
                            try:
                                out_path = case_dir / Path(case_part.name + '.yaml')
                                with out_path.open(file_mode) as f:
                                    yaml.dump(case_part.data, f)
                            except IOError as e:
                                sys.exit(f'Error when dumping test "{case_dir}", part "{case_part.name}": {e}')
                        # if out_kind == "ssz":
                        #     # TODO write SSZ as binary file too.
                        #     out_path = case_dir / Path(name + '.ssz')
                except Exception as e:
                    print(f"ERROR: failed to generate vector(s) for test {case_dir}: {e}")
        print(f"completed {generator_name}")
