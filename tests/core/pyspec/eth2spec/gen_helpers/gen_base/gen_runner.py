import argparse
import functools
import multiprocessing
import os
import shutil
import signal
import sys
import threading
import time
import uuid

from pathlib import Path
from typing import Any, AnyStr, Callable, Iterable

from eth_utils import encode_hex
from pathos.multiprocessing import ProcessingPool as Pool
from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text
from ruamel.yaml import YAML
from snappy import compress

from eth2spec.test import context
from eth2spec.test.exceptions import SkippedTest

from .gen_typing import TestCase, TestProvider

###############################################################################
# Global settings
###############################################################################

# Flag that the runner does NOT run test via pytest
context.is_pytest = False

###############################################################################
# Helper functions
###############################################################################


@functools.lru_cache(maxsize=None)
def human_time(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


@functools.lru_cache(maxsize=None)
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


@functools.lru_cache(maxsize=None)
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


def get_shared_prefix(test_cases, min_segments=3):
    assert test_cases, "no test cases provided"

    fields = [
        "preset_name",
        "fork_name",
        "runner_name",
        "handler_name",
    ]

    prefix = []
    for i, field in enumerate(fields):
        values = {getattr(tc, field) for tc in test_cases}
        if len(values) == 1:
            prefix.append(values.pop())
        elif i < min_segments:
            prefix.append("*")
        else:
            break

    return "::".join(prefix)


def dump_yaml_fn(data: Any, name: str, yaml_encoder: YAML):
    def dump(case_path: Path):
        out_path = case_path / Path(name + ".yaml")
        with out_path.open("w") as f:
            yaml_encoder.dump(data, f)
            f.close()

    return dump


def output_part(test_case: TestCase, out_kind: str, name: str, fn: Callable[[Path], None]):
    # make sure the test case directory is created before any test part is written.
    test_case.dir.mkdir(parents=True, exist_ok=True)
    try:
        fn(test_case.dir)
    except (IOError, ValueError) as e:
        print(f"[ERROR] failed to dump {test_case.dir}, part {name}, kind {out_kind}: {e}")
        sys.exit(1)


def execute_test(test_case: TestCase):
    meta = dict()
    result = test_case.case_fn()
    for name, out_kind, data in result:
        if out_kind == "meta":
            meta[name] = data
        elif out_kind == "cfg":
            output_part(test_case, out_kind, name, dump_yaml_fn(data, name, get_cfg_yaml()))
        elif out_kind == "data":
            output_part(test_case, out_kind, name, dump_yaml_fn(data, name, get_default_yaml()))
        elif out_kind == "ssz":
            output_part(test_case, out_kind, name, dump_ssz_fn(data, name))
        else:
            raise ValueError("Unknown out_kind %s" % out_kind)

    if len(meta) != 0:
        output_part(test_case, "data", "meta", dump_yaml_fn(meta, "meta", get_default_yaml()))


def dump_ssz_fn(data: AnyStr, name: str):
    def dump(case_path: Path):
        out_path = case_path / Path(name + ".ssz_snappy")
        compressed = compress(data)
        with out_path.open("wb") as f:
            f.write(compressed)

    return dump


def parse_arguments(generator_name):
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
    parser.add_argument(
        "--threads",
        type=int,
        default=os.cpu_count(),
        help="Generate tests N threads, defaults to all available.",
    )
    parser.add_argument(
        "--time-threshold-to-print",
        type=float,
        default=1.0,
        help="Print a log if the test takes longer than this.",
    )
    return parser.parse_args()


###############################################################################
# Main logic
###############################################################################


def run_generator(generator_name: str, test_providers: Iterable[TestProvider]):
    args = parse_arguments(generator_name)

    # Bail here if we are checking modules.
    if args.modcheck:
        return

    console = Console()

    # Gracefully handle Ctrl+C: restore cursor and exit immediately
    def _handle_sigint(signum, frame):
        console.show_cursor()
        os._exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    output_dir = args.output_dir

    def debug_print(msg):
        if args.verbose:
            print(msg)

    debug_print(f"Generating tests into {output_dir}")

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

    provider_start = time.time()

    all_test_cases = []
    for tprov in test_providers:
        # Runs anything that we don't want to repeat for every test case.
        tprov.prepare()

        for test_case in tprov.make_cases():
            # If preset list is assigned, filter by presets.
            if len(presets) != 0 and test_case.preset_name not in presets:
                debug_print(f"Filtered: {test_case.get_identifier()}")
                continue

            # If fork list is assigned, filter by forks.
            if len(forks) != 0 and test_case.fork_name not in forks:
                debug_print(f"Filtered: {test_case.get_identifier()}")
                continue

            # If cases list is assigned, filter by cases.
            if len(cases) != 0 and not any(s in test_case.case_name for s in cases):
                debug_print(f"Filtered: {test_case.get_identifier()}")
                continue

            test_case.set_output_dir(output_dir)
            if test_case.dir.exists():
                shutil.rmtree(test_case.dir)
            all_test_cases.append(test_case)

    if len(all_test_cases) == 0:
        return

    tests_prefix = get_shared_prefix(all_test_cases)

    def worker_function(data):
        test_case, active_tasks = data
        key = (uuid.uuid4(), test_case.get_identifier())
        active_tasks[key] = time.time()
        try:
            execute_test(test_case)
            debug_print(f"Generated: {test_case.get_identifier()}")
        except SkippedTest:
            debug_print(f"Skipped: {test_case.get_identifier()}")
            return
        finally:
            del active_tasks[key]

    def display_active_tasks(active_tasks, total_tasks, completed, width):
        init_time = time.time()
        with Live(refresh_per_second=4, console=console) as live:
            while True:
                remaining = total_tasks - completed.value
                if remaining == 0:
                    elapsed = time.time() - init_time
                    live.update(
                        Text.from_markup(f"Completed {tests_prefix} in {human_time(elapsed)}")
                    )
                    break
                table = Table(box=box.ROUNDED)
                elapsed = time.time() - init_time
                table.add_column(
                    f"Test (gen={tests_prefix}, threads={args.threads}, total={total_tasks}, remaining={remaining}, time={human_time(elapsed)})",
                    style="cyan",
                    no_wrap=True,
                    width=width,
                )
                table.add_column("Elapsed Time", justify="right", style="magenta")
                for k, start in sorted(active_tasks.items(), key=lambda x: x[1]):
                    elapsed = time.time() - start
                    table.add_row(k[1], f"{human_time(elapsed)}")
                live.update(table)
                time.sleep(0.1)

    with multiprocessing.Manager() as manager:
        total_tasks = len(all_test_cases)
        active_tasks = manager.dict()
        completed = manager.Value("i", 0)
        width = max([len(t.get_identifier()) for t in all_test_cases])

        if not args.verbose:
            display_thread = threading.Thread(
                target=display_active_tasks,
                args=(active_tasks, total_tasks, completed, width),
                daemon=True,
            )
            display_thread.start()

        inputs = [(t, active_tasks) for t in all_test_cases]
        for _ in Pool(processes=args.threads).uimap(worker_function, inputs):
            completed.value += 1

        if not args.verbose:
            display_thread.join()

    elapsed = round(time.time() - provider_start, 2)
    debug_print(f"Completed generation of {tests_prefix} in {elapsed} seconds")
