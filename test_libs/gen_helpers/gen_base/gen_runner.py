import argparse
from pathlib import Path
import sys
from typing import Iterable

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
        help="if set re-generate and overwrite test files if they already exist",
    )
    parser.add_argument(
        "-c",
        "--configs-path",
        dest="configs_path",
        required=True,
        type=validate_configs_dir,
        help="specify the path of the configs directory",
    )
    parser.add_argument(
        "-l",
        "--config-list",
        dest="config_list",
        nargs='*',
        type=str,
        required=False,
        help="specify configs to run with. Allows all if no config names are specified.",
    )

    args = parser.parse_args()
    output_dir = args.output_dir
    if not args.force:
        file_mode = "x"
    else:
        file_mode = "w"

    yaml = YAML(pure=True)
    yaml.default_flow_style = None

    print(f"Generating tests into {output_dir}")
    print(f"Reading configs from {args.configs_path}")

    configs = args.config_list
    if len(configs) != 0:
        print(f"Filtering test-generator runs to only include configs: {', '.join(configs)}")

    for tprov in test_providers:
        # loads configuration etc.
        config_name = tprov.prepare(args.configs_path)
        if len(configs) != 0 and config_name not in configs:
            print(f"skipping tests with config '{config_name}' since it is filtered out")
            continue

        print(f"generating tests with config '{config_name}' ...")
        for test_case in tprov.make_cases():
            case_dir = Path(output_dir) / Path(config_name) / Path(test_case.fork_name) \
                       / Path(test_case.runner_name) / Path(test_case.handler_name) \
                       / Path(test_case.suite_name) / Path(test_case.case_name)

            if case_dir.exists():
                if not args.force:
                    print(f'Skipping already existing test: {case_dir}')
                    continue
                print(f'Warning, output directory {case_dir} already exist,'
                      f' old files are not deleted but will be overwritten when a new version is produced')

            print(f'Generating test: {case_dir}')
            try:
                case_dir.mkdir(parents=True, exist_ok=True)
                meta = dict()
                for (name, out_kind, data) in test_case.case_fn():
                    if out_kind == "meta":
                        meta[name] = data
                    if out_kind == "data":
                        try:
                            out_path = case_dir / Path(name + '.yaml')
                            with out_path.open(file_mode) as f:
                                yaml.dump(data, f)
                        except IOError as e:
                            sys.exit(f'Error when dumping test "{case_dir}", part "{name}", kind "{out_kind}": {e}')
                    if out_kind == "ssz":
                        try:
                            out_path = case_dir / Path(name + '.ssz')
                            with out_path.open(file_mode + 'b') as f:  # write in raw binary mode
                                f.write(data)
                        except IOError as e:
                            sys.exit(f'Error when dumping test "{case_dir}", part "{name}", kind "{out_kind}": {e}')
                # Once all meta data is collected (if any), write it to a meta data file.
                if len(meta) != 0:
                    try:
                        out_path = case_dir / Path('meta.yaml')
                        with out_path.open(file_mode) as f:
                            yaml.dump(meta, f)
                    except IOError as e:
                        sys.exit(f'Error when dumping test "{case_dir}" meta data": {e}')

            except Exception as e:
                print(f"ERROR: failed to generate vector(s) for test {case_dir}: {e}")
    print(f"completed {generator_name}")
