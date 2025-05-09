import multiprocessing
import shutil
import threading
import time
import uuid

from typing import Any, Iterable

from pathos.multiprocessing import ProcessingPool as Pool
from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from eth2spec.test import context
from eth2spec.test.exceptions import SkippedTest

from .args import parse_arguments
from .dumper import Dumper
from .gen_typing import TestCase, TestProvider
from .utils import format_duration, install_sigint_handler

# Flag that the runner does NOT run test via pytest
context.is_pytest = False


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


def execute_test(test_case: TestCase, dumper: Dumper):
    """Execute a test and write the outputs to storage."""
    meta: dict[str, Any] = {}
    for name, kind, data in test_case.case_fn():
        if kind == "meta":
            meta[name] = data
        else:
            try:
                method = getattr(dumper, f"dump_{kind}")
            except AttributeError:
                raise ValueError(f"Unknown kind {kind!r}")
            method(test_case, name, data)

    if meta:
        dumper.dump_meta(test_case, meta)


def run_generator(generator_name: str, test_providers: Iterable[TestProvider]):
    start_time = time.time()
    args = parse_arguments(generator_name)

    # Bail here if we are checking modules.
    if args.modcheck:
        return

    def debug_print(msg):
        """Only print if verbose is enabled."""
        if args.verbose:
            print(msg)

    console = Console()
    dumper = Dumper()

    # Gracefully handle Ctrl+C
    install_sigint_handler(console)

    test_cases = []
    for tprov in test_providers:
        for test_case in tprov.make_cases():
            # Check if the test case should be filtered out
            if len(args.presets) != 0 and test_case.preset_name not in args.presets:
                debug_print(f"Filtered: {test_case.get_identifier()}")
                continue
            if len(args.forks) != 0 and test_case.fork_name not in args.forks:
                debug_print(f"Filtered: {test_case.get_identifier()}")
                continue
            if len(args.cases) != 0 and not any(s in test_case.case_name for s in args.cases):
                debug_print(f"Filtered: {test_case.get_identifier()}")
                continue

            # Set the output dir and add this to out list
            test_case.set_output_dir(args.output_dir)
            if test_case.dir.exists():
                shutil.rmtree(test_case.dir)
            test_cases.append(test_case)

    if len(test_cases) == 0:
        return

    debug_print(f"Generating tests into {args.output_dir}")
    tests_prefix = get_shared_prefix(test_cases)

    def worker_function(data):
        """Execute a test case and update active tests."""
        test_case, active_tests = data
        key = (uuid.uuid4(), test_case.get_identifier())
        active_tests[key] = time.time()
        try:
            execute_test(test_case, dumper)
            debug_print(f"Generated: {test_case.get_identifier()}")
            return "generated"
        except SkippedTest:
            debug_print(f"Skipped: {test_case.get_identifier()}")
            return "skipped"
        finally:
            del active_tests[key]

    def display_active_tests(active_tests, total_tasks, completed, skipped, width):
        """Display a table of active tests."""
        with Live(console=console) as live:
            while True:
                remaining = total_tasks - completed.value
                if remaining == 0:
                    # Show a final status when the queue is empty
                    # This is better than showing an empty table
                    live.update(
                        Text.from_markup(
                            f"Completed {tests_prefix} in {format_duration(time.time() - start_time)}"
                        )
                    )
                    break

                info = ", ".join(
                    [
                        f"gen={tests_prefix}",
                        f"threads={args.threads}",
                        f"total={total_tasks}",
                        f"skipped={skipped.value}",
                        f"remaining={remaining}",
                        f"time={format_duration(time.time() - start_time)}",
                    ]
                )

                table = Table(box=box.ROUNDED)
                table.add_column(f"Test ({info})", style="cyan", no_wrap=True, width=width)
                table.add_column("Elapsed Time", justify="right", style="magenta")
                for k, start in sorted(active_tests.items(), key=lambda x: x[1]):
                    table.add_row(k[1], f"{format_duration(time.time() - start)}")
                live.update(table)
                time.sleep(0.1)

    # Generate all of the test cases
    with multiprocessing.Manager() as manager:
        active_tests = manager.dict()
        completed = manager.Value("i", 0)
        skipped = manager.Value("i", 0)
        width = max([len(t.get_identifier()) for t in test_cases])

        if not args.verbose:
            display_thread = threading.Thread(
                target=display_active_tests,
                args=(active_tests, len(test_cases), completed, skipped, width),
                daemon=True,
            )
            display_thread.start()

        # Map each test case to a thread worker
        inputs = [(t, active_tests) for t in test_cases]
        for result in Pool(processes=args.threads).uimap(worker_function, inputs):
            if result == "skipped":
                skipped.value += 1
            completed.value += 1

        if not args.verbose:
            display_thread.join()

    elapsed = round(time.time() - start_time, 2)
    debug_print(f"Completed generation of {tests_prefix} in {elapsed} seconds")
