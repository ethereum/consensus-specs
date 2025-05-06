from dataclasses import (
    dataclass,
    field,
)
import os
import time
import shutil
import argparse
from pathlib import Path
import sys
import json
from typing import Iterable, AnyStr, Any, Callable
import traceback
from collections import namedtuple

from ruamel.yaml import (
    YAML,
)

from filelock import FileLock
from snappy import compress
from pathos.multiprocessing import ProcessingPool as Pool

from eth_utils import encode_hex

from eth2spec.test import context
from eth2spec.test.exceptions import SkippedTest

from .gen_typing import TestProvider
from .settings import (
    GENERATOR_MODE,
    MODE_MULTIPROCESSING,
    MODE_SINGLE_PROCESS,
    NUM_PROCESS,
    TIME_THRESHOLD_TO_PRINT,
)


# Flag that the runner does NOT run test via pytest
context.is_pytest = False


@dataclass
class Diagnostics(object):
    collected_test_count: int = 0
    generated_test_count: int = 0
    skipped_test_count: int = 0
    test_identifiers: list = field(default_factory=list)


TestCaseParams = namedtuple(
    "TestCaseParams",
    [
        "test_case",
        "case_dir",
        "log_file",
        "file_mode",
    ],
)


def worker_function(item):
    return generate_test_vector(*item)


def get_default_yaml():
    yaml = YAML(pure=True)
    yaml.default_flow_style = None

    def _represent_none(self, _):
        return self.represent_scalar("tag:yaml.org,2002:null", "null")

    def _represent_str(self, data):
        if data.startswith("0x"):
            # Without this, a zero-byte hex string is represented without quotes.
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="'")
        return self.represent_str(data)

    yaml.representer.add_representer(type(None), _represent_none)
    yaml.representer.add_representer(str, _represent_str)

    return yaml


def get_cfg_yaml():
    # Spec config is using a YAML subset
    cfg_yaml = YAML(pure=True)
    cfg_yaml.default_flow_style = False  # Emit separate line for each key

    def cfg_represent_bytes(self, data):
        return self.represent_int(encode_hex(data))

    cfg_yaml.representer.add_representer(bytes, cfg_represent_bytes)

    def cfg_represent_quoted_str(self, data):
        return self.represent_scalar("tag:yaml.org,2002:str", data, style="'")

    cfg_yaml.representer.add_representer(context.quoted_str, cfg_represent_quoted_str)
    return cfg_yaml


def validate_output_dir(path_str):
    path = Path(path_str)

    if not path.exists():
        raise argparse.ArgumentTypeError("Output directory must exist")

    if not path.is_dir():
        raise argparse.ArgumentTypeError("Output path must lead to a directory")

    return path


def get_test_case_dir(test_case, output_dir):
    return (
        Path(output_dir)
        / Path(test_case.preset_name)
        / Path(test_case.fork_name)
        / Path(test_case.runner_name)
        / Path(test_case.handler_name)
        / Path(test_case.suite_name)
        / Path(test_case.case_name)
    )


def get_test_identifier(test_case):
    return "::".join(
        [
            test_case.preset_name,
            test_case.fork_name,
            test_case.runner_name,
            test_case.handler_name,
            test_case.suite_name,
            test_case.case_name,
        ]
    )


def get_incomplete_tag_file(case_dir):
    return case_dir / "INCOMPLETE"


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
        description=f"Generate YAML test suite files for {generator_name}.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        required=True,
        type=validate_output_dir,
        help="Directory into which the generated YAML files will be dumped.",
    )
    parser.add_argument(
        "--preset-list",
        dest="preset_list",
        nargs="*",
        type=str,
        required=False,
        help="Specify presets to run with. Allows all if no preset names are specified.",
    )
    parser.add_argument(
        "--fork-list",
        dest="fork_list",
        nargs="*",
        type=str,
        required=False,
        help="Specify forks to run with. Allows all if no fork names are specified.",
    )
    parser.add_argument(
        "--modcheck",
        action="store_true",
        default=False,
        help="Check generator modules, do not run any tests.",
    )
    parser.add_argument(
        "--case-list",
        dest="case_list",
        nargs="*",
        type=str,
        required=False,
        help="Specify test cases to run with. Allows all if no test case names are specified.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print more information to the console.",
    )
    args = parser.parse_args()

    # Bail here if we are checking modules.
    if args.modcheck:
        return

    output_dir = args.output_dir
    file_mode = "w"
    log_file = Path(output_dir) / "testgen_error_log.txt"

    def debug_print(msg):
        if args.verbose:
            print(msg)

    debug_print(f"Generating tests into {output_dir}")
    debug_print(f"Error log file: {log_file}")

    # preset_list arg
    presets = args.preset_list
    if presets is None:
        presets = []

    if len(presets) != 0:
        debug_print(f"Filtering test-generator runs to only include presets: {', '.join(presets)}")

    # fork_list arg
    forks = args.fork_list
    if forks is None:
        forks = []

    if len(forks) != 0:
        debug_print(f"Filtering test-generator runs to only include forks: {', '.join(forks)}")

    # case_list arg
    cases = args.case_list
    if cases is None:
        cases = []

    if len(cases) != 0:
        debug_print(f"Filtering test-generator runs to only include test cases: {', '.join(cases)}")

    diagnostics_obj = Diagnostics()
    provider_start = time.time()

    if GENERATOR_MODE == MODE_MULTIPROCESSING:
        all_test_case_params = []

    for tprov in test_providers:
        # Runs anything that we don't want to repeat for every test case.
        tprov.prepare()

        for test_case in tprov.make_cases():
            # If preset list is assigned, filter by presets.
            if len(presets) != 0 and test_case.preset_name not in presets:
                print(f"Skipped: {get_test_identifier(test_case)}")
                continue

            # If fork list is assigned, filter by forks.
            if len(forks) != 0 and test_case.fork_name not in forks:
                print(f"Skipped: {get_test_identifier(test_case)}")
                continue

            # If cases list is assigned, filter by cases.
            if len(cases) != 0 and test_case.case_name not in cases:
                print(f"Skipped: {get_test_identifier(test_case)}")
                continue

            print(f"Collected: {get_test_identifier(test_case)}")
            diagnostics_obj.collected_test_count += 1

            case_dir = get_test_case_dir(test_case, output_dir)
            if case_dir.exists():
                # Clear the existing case_dir folder
                shutil.rmtree(case_dir)

            if GENERATOR_MODE == MODE_SINGLE_PROCESS:
                result, info = generate_test_vector(test_case, case_dir, log_file, file_mode)
                if isinstance(result, int):
                    # Skipped or error
                    debug_print(info)
                elif isinstance(result, str):
                    # Success
                    if info > TIME_THRESHOLD_TO_PRINT:
                        debug_print(f"^^^ Slow test, took {info} seconds ^^^")
                write_result_into_diagnostics_obj(result, diagnostics_obj)
            elif GENERATOR_MODE == MODE_MULTIPROCESSING:
                item = TestCaseParams(test_case, case_dir, log_file, file_mode)
                all_test_case_params.append(item)

    if GENERATOR_MODE == MODE_MULTIPROCESSING:
        with Pool(processes=NUM_PROCESS) as pool:
            results = pool.map(worker_function, iter(all_test_case_params))

        for result in results:
            write_result_into_diagnostics_obj(result[0], diagnostics_obj)

    provider_end = time.time()
    span = round(provider_end - provider_start, 2)

    summary_message = f"Completed generation of {generator_name} with {diagnostics_obj.generated_test_count} tests"
    summary_message += f" ({diagnostics_obj.skipped_test_count} skipped tests)"
    if span > TIME_THRESHOLD_TO_PRINT:
        summary_message += f" in {span} seconds"
    debug_print(summary_message)

    diagnostics_output = {
        "collected_test_count": diagnostics_obj.collected_test_count,
        "generated_test_count": diagnostics_obj.generated_test_count,
        "skipped_test_count": diagnostics_obj.skipped_test_count,
        "test_identifiers": diagnostics_obj.test_identifiers,
        "durations": [f"{span} seconds"],
    }
    diagnostics_path = Path(os.path.join(output_dir, "diagnostics_obj.json"))
    diagnostics_lock = FileLock(os.path.join(output_dir, "diagnostics_obj.json.lock"))
    with diagnostics_lock:
        diagnostics_path.touch(exist_ok=True)
        if os.path.getsize(diagnostics_path) == 0:
            with open(diagnostics_path, "w+") as f:
                json.dump(diagnostics_output, f)
        else:
            with open(diagnostics_path, "r+") as f:
                existing_diagnostics = json.load(f)
                for k, v in diagnostics_output.items():
                    existing_diagnostics[k] += v
            with open(diagnostics_path, "w+") as f:
                json.dump(existing_diagnostics, f)
        debug_print(f"Wrote diagnostics_obj to {diagnostics_path}")


def generate_test_vector(test_case, case_dir, log_file, file_mode):
    cfg_yaml = get_cfg_yaml()
    yaml = get_default_yaml()

    written_part = False

    test_start = time.time()

    # Add `INCOMPLETE` tag file to indicate that the test generation has not completed.
    incomplete_tag_file = get_incomplete_tag_file(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    with incomplete_tag_file.open("w") as f:
        f.write("\n")

    result = None
    try:
        meta = dict()
        try:
            written_part, meta = execute_test(
                test_case, case_dir, meta, log_file, file_mode, cfg_yaml, yaml
            )
        except SkippedTest as e:
            result = 0  # 0 means skipped
            shutil.rmtree(case_dir)
            return result, e

        # Once all meta data is collected (if any), write it to a meta data file.
        if len(meta) != 0:
            written_part = True
            output_part(
                case_dir, log_file, "data", "meta", dump_yaml_fn(meta, "meta", file_mode, yaml)
            )

    except Exception as e:
        result = -1  # -1 means error
        error_message = f"[ERROR] failed to generate vector(s) for test {case_dir}: {e}"
        # Write to error log file
        with log_file.open("a+") as f:
            f.write(error_message)
            traceback.print_exc(file=f)
            f.write("\n")
        print(error_message)
        traceback.print_exc()
    else:
        # If no written_part, the only file was incomplete_tag_file. Clear the existing case_dir folder.
        if not written_part:
            print(f"[Error] test case {case_dir} did not produce any written_part")
            shutil.rmtree(case_dir)
            result = -1
        else:
            result = get_test_identifier(test_case)
            # Only remove `INCOMPLETE` tag file
            os.remove(incomplete_tag_file)
    test_end = time.time()
    span = round(test_end - test_start, 2)
    return result, span


def write_result_into_diagnostics_obj(result, diagnostics_obj):
    if result == -1:  # error
        pass
    elif result == 0:
        diagnostics_obj.skipped_test_count += 1
    elif result is not None:
        diagnostics_obj.generated_test_count += 1
        diagnostics_obj.test_identifiers.append(result)
    else:
        raise Exception(f"Unexpected result: {result}")


def dump_yaml_fn(data: Any, name: str, file_mode: str, yaml_encoder: YAML):
    def dump(case_path: Path):
        out_path = case_path / Path(name + ".yaml")
        with out_path.open(file_mode) as f:
            yaml_encoder.dump(data, f)
            f.close()

    return dump


def output_part(
    case_dir,
    log_file,
    out_kind: str,
    name: str,
    fn: Callable[
        [
            Path,
        ],
        None,
    ],
):
    # make sure the test case directory is created before any test part is written.
    case_dir.mkdir(parents=True, exist_ok=True)
    try:
        fn(case_dir)
    except (IOError, ValueError) as e:
        error_message = (
            f'[Error] error when dumping test "{case_dir}", part "{name}", kind "{out_kind}": {e}'
        )
        # Write to error log file
        with log_file.open("a+") as f:
            f.write(error_message)
            traceback.print_exc(file=f)
            f.write("\n")
        print(error_message)
        sys.exit(error_message)


def execute_test(test_case, case_dir, meta, log_file, file_mode, cfg_yaml, yaml):
    result = test_case.case_fn()
    written_part = False
    for name, out_kind, data in result:
        written_part = True
        if out_kind == "meta":
            meta[name] = data
        elif out_kind == "cfg":
            output_part(
                case_dir, log_file, out_kind, name, dump_yaml_fn(data, name, file_mode, cfg_yaml)
            )
        elif out_kind == "data":
            output_part(
                case_dir, log_file, out_kind, name, dump_yaml_fn(data, name, file_mode, yaml)
            )
        elif out_kind == "ssz":
            output_part(case_dir, log_file, out_kind, name, dump_ssz_fn(data, name, file_mode))
        else:
            raise ValueError("Unknown out_kind %s" % out_kind)

    return written_part, meta


def dump_ssz_fn(data: AnyStr, name: str, file_mode: str):
    def dump(case_path: Path):
        out_path = case_path / Path(name + ".ssz_snappy")
        compressed = compress(data)
        with out_path.open(file_mode + "b") as f:  # write in raw binary mode
            f.write(compressed)

    return dump
