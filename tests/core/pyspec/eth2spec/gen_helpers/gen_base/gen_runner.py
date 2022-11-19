from eth_utils import encode_hex
import os
import time
import shutil
import argparse
from pathlib import Path
import sys
import json
from typing import Iterable, AnyStr, Any, Callable
import traceback
from ruamel.yaml import (
    YAML,
)

from filelock import FileLock
from snappy import compress

from eth2spec.test import context
from eth2spec.test.exceptions import SkippedTest

from .gen_typing import TestProvider


# Flag that the runner does NOT run test via pytest
context.is_pytest = False


TIME_THRESHOLD_TO_PRINT = 1.0  # seconds


def validate_output_dir(path_str):
    path = Path(path_str)

    if not path.exists():
        raise argparse.ArgumentTypeError("Output directory must exist")

    if not path.is_dir():
        raise argparse.ArgumentTypeError("Output path must lead to a directory")

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
        "-l",
        "--preset-list",
        dest="preset_list",
        nargs='*',
        type=str,
        required=False,
        help="specify presets to run with. Allows all if no preset names are specified.",
    )
    parser.add_argument(
        "-c",
        "--collect-only",
        action="store_true",
        default=False,
        help="if set only print tests to generate, do not actually run the test and dump the target data",
    )

    args = parser.parse_args()
    output_dir = args.output_dir
    if not args.force:
        file_mode = "x"
    else:
        file_mode = "w"

    yaml = YAML(pure=True)
    yaml.default_flow_style = None

    def _represent_none(self, _):
        return self.represent_scalar('tag:yaml.org,2002:null', 'null')

    yaml.representer.add_representer(type(None), _represent_none)

    # Spec config is using a YAML subset
    cfg_yaml = YAML(pure=True)
    cfg_yaml.default_flow_style = False  # Emit separate line for each key

    def cfg_represent_bytes(self, data):
        return self.represent_int(encode_hex(data))

    cfg_yaml.representer.add_representer(bytes, cfg_represent_bytes)

    def cfg_represent_quoted_str(self, data):
        return self.represent_scalar(u'tag:yaml.org,2002:str', data, style="'")

    cfg_yaml.representer.add_representer(context.quoted_str, cfg_represent_quoted_str)

    log_file = Path(output_dir) / 'testgen_error_log.txt'

    print(f"Generating tests into {output_dir}")
    print(f'Error log file: {log_file}')

    presets = args.preset_list
    if presets is None:
        presets = []

    if len(presets) != 0:
        print(f"Filtering test-generator runs to only include presets: {', '.join(presets)}")

    collect_only = args.collect_only
    collected_test_count = 0
    generated_test_count = 0
    skipped_test_count = 0
    test_identifiers = []

    provider_start = time.time()
    for tprov in test_providers:
        if not collect_only:
            # runs anything that we don't want to repeat for every test case.
            tprov.prepare()

        for test_case in tprov.make_cases():
            # If preset list is assigned, filter by presets.
            if len(presets) != 0 and test_case.preset_name not in presets:
                continue

            case_dir = (
                Path(output_dir) / Path(test_case.preset_name) / Path(test_case.fork_name)
                / Path(test_case.runner_name) / Path(test_case.handler_name)
                / Path(test_case.suite_name) / Path(test_case.case_name)
            )
            collected_test_count += 1
            print(f"Collected test at: {case_dir}")

            incomplete_tag_file = case_dir / "INCOMPLETE"

            if case_dir.exists():
                if not args.force and not incomplete_tag_file.exists():
                    skipped_test_count += 1
                    print(f'Skipping already existing test: {case_dir}')
                    continue
                else:
                    print(f'Warning, output directory {case_dir} already exist,'
                          f' old files will be deleted and it will generate test vector files with the latest version')
                    # Clear the existing case_dir folder
                    shutil.rmtree(case_dir)

            print(f'Generating test: {case_dir}')
            test_start = time.time()

            written_part = False

            # Add `INCOMPLETE` tag file to indicate that the test generation has not completed.
            case_dir.mkdir(parents=True, exist_ok=True)
            with incomplete_tag_file.open("w") as f:
                f.write("\n")

            try:
                def output_part(out_kind: str, name: str, fn: Callable[[Path, ], None]):
                    # make sure the test case directory is created before any test part is written.
                    case_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        fn(case_dir)
                    except IOError as e:
                        error_message = (
                            f'[Error] error when dumping test "{case_dir}", part "{name}", kind "{out_kind}": {e}'
                        )
                        # Write to error log file
                        with log_file.open("a+") as f:
                            f.write(error_message)
                            traceback.print_exc(file=f)
                            f.write('\n')

                        sys.exit(error_message)

                meta = dict()

                try:
                    for (name, out_kind, data) in test_case.case_fn():
                        written_part = True
                        if out_kind == "meta":
                            meta[name] = data
                        elif out_kind == "cfg":
                            output_part(out_kind, name, dump_yaml_fn(data, name, file_mode, cfg_yaml))
                        elif out_kind == "data":
                            output_part(out_kind, name, dump_yaml_fn(data, name, file_mode, yaml))
                        elif out_kind == "ssz":
                            output_part(out_kind, name, dump_ssz_fn(data, name, file_mode))
                        else:
                            assert False  # Unknown kind
                except SkippedTest as e:
                    print(e)
                    skipped_test_count += 1
                    shutil.rmtree(case_dir)
                    continue

                # Once all meta data is collected (if any), write it to a meta data file.
                if len(meta) != 0:
                    written_part = True
                    output_part("data", "meta", dump_yaml_fn(meta, "meta", file_mode, yaml))

                if not written_part:
                    print(f"test case {case_dir} did not produce any test case parts")
            except Exception as e:
                error_message = f"[ERROR] failed to generate vector(s) for test {case_dir}: {e}"
                # Write to error log file
                with log_file.open("a+") as f:
                    f.write(error_message)
                    traceback.print_exc(file=f)
                    f.write('\n')
                traceback.print_exc()
            else:
                # If no written_part, the only file was incomplete_tag_file. Clear the existing case_dir folder.
                if not written_part:
                    shutil.rmtree(case_dir)
                else:
                    generated_test_count += 1
                    test_identifier = "::".join([
                        test_case.preset_name,
                        test_case.fork_name,
                        test_case.runner_name,
                        test_case.handler_name,
                        test_case.suite_name,
                        test_case.case_name
                    ])
                    test_identifiers.append(test_identifier)
                    # Only remove `INCOMPLETE` tag file
                    os.remove(incomplete_tag_file)
            test_end = time.time()
            span = round(test_end - test_start, 2)
            if span > TIME_THRESHOLD_TO_PRINT:
                print(f'    - generated in {span} seconds')

    provider_end = time.time()
    span = round(provider_end - provider_start, 2)

    if collect_only:
        print(f"Collected {collected_test_count} tests in total")
    else:
        summary_message = f"completed generation of {generator_name} with {generated_test_count} tests"
        summary_message += f" ({skipped_test_count} skipped tests)"
        if span > TIME_THRESHOLD_TO_PRINT:
            summary_message += f" in {span} seconds"
        print(summary_message)
    diagnostics = {
        "collected_test_count": collected_test_count,
        "generated_test_count": generated_test_count,
        "skipped_test_count": skipped_test_count,
        "test_identifiers": test_identifiers,
        "durations": [f"{span} seconds"],
    }
    diagnostics_path = Path(os.path.join(output_dir, "diagnostics.json"))
    diagnostics_lock = FileLock(os.path.join(output_dir, "diagnostics.json.lock"))
    with diagnostics_lock:
        diagnostics_path.touch(exist_ok=True)
        if os.path.getsize(diagnostics_path) == 0:
            with open(diagnostics_path, "w+") as f:
                json.dump(diagnostics, f)
        else:
            with open(diagnostics_path, "r+") as f:
                existing_diagnostics = json.load(f)
                for k, v in diagnostics.items():
                    existing_diagnostics[k] += v
            with open(diagnostics_path, "w+") as f:
                json.dump(existing_diagnostics, f)
        print(f"wrote diagnostics to {diagnostics_path}")


def dump_yaml_fn(data: Any, name: str, file_mode: str, yaml_encoder: YAML):
    def dump(case_path: Path):
        out_path = case_path / Path(name + '.yaml')
        with out_path.open(file_mode) as f:
            yaml_encoder.dump(data, f)
    return dump


def dump_ssz_fn(data: AnyStr, name: str, file_mode: str):
    def dump(case_path: Path):
        out_path = case_path / Path(name + '.ssz_snappy')
        compressed = compress(data)
        with out_path.open(file_mode + 'b') as f:  # write in raw binary mode
            f.write(compressed)
    return dump
