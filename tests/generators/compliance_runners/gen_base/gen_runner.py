import multiprocessing
import shutil
import threading
import time
import uuid
from collections.abc import Iterable

import psutil
from pathos.multiprocessing import ProcessingPool as Pool
from rich import box
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from eth_consensus_specs.test import context  # noqa: F401 — imported to break circular import chain
from eth_consensus_specs.test.exceptions import SkippedTest
from tests.infra.dumper import Dumper

from .args import parse_arguments
from .gen_typing import TestCase, TestCaseResult, TestGroup
from .utils import install_sigint_handler, time_since


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


def display_test_summary(
    console: Console,
    total_found: int,
    total_selected: int,
    total_completed: int,
    total_skipped: int,
    elapsed_time: float,
):
    """Display a rich formatted summary table of test generation results."""
    summary_table = Table(
        title="Reference Test Generation Summary", box=box.ROUNDED, title_style="bold blue"
    )
    summary_table.add_column("Metric", style="cyan", justify="left")
    summary_table.add_column("Count", style="green", justify="right")
    summary_table.add_column("Percentage", style="yellow", justify="right")

    # Calculate counts and percentages
    total_filtered = total_found - total_selected
    filtered_pct = (total_filtered / total_found * 100) if total_found > 0 else 0
    selected_pct = (total_selected / total_found * 100) if total_found > 0 else 0
    completed_pct = (total_completed / total_selected * 100) if total_selected > 0 else 0
    skipped_pct = (total_skipped / total_selected * 100) if total_selected > 0 else 0

    summary_table.add_row("Found", str(total_found), "100.0%")
    summary_table.add_row("Filtered", str(total_filtered), f"{filtered_pct:.1f}%")
    summary_table.add_row("Selected", str(total_selected), f"{selected_pct:.1f}%")
    summary_table.add_row("Completed", str(total_completed), f"{completed_pct:.1f}%")
    summary_table.add_row("Skipped", str(total_skipped), f"{skipped_pct:.1f}%")
    summary_table.add_row("Time", f"{elapsed_time:.2f}s", "")

    console.print()
    console.print(summary_table)
    console.print()


def dump_test_case_result(test_case_result: TestCaseResult, dumper: Dumper) -> None:
    """Write a collected test case result to storage."""
    test_case = test_case_result.test_case

    for name, kind, data in test_case_result.case_parts:
        method = getattr(dumper, f"dump_{kind}", None)
        if method is None:
            raise ValueError(f"Unknown kind {kind!r}")
        method(test_case.dir, name, data)

    if test_case_result.meta:
        dumper.dump_meta(test_case.dir, test_case_result.meta)

    # Always write manifest.yml for every test case
    manifest_data = {
        "preset": test_case.preset_name,
        "fork": test_case.fork_name,
        "runner": test_case.runner_name,
        "handler": test_case.handler_name,
        "suite": test_case.suite_name,
        "case": test_case.case_name,
    }
    dumper.dump_manifest(test_case.dir, manifest_data)


def execute_test_group(
    test_group: TestGroup,
    dumper: Dumper,
) -> None:
    """Execute a test group and write all of its selected test cases to storage."""
    for test_case_result in test_group.group_fn():
        dump_test_case_result(test_case_result, dumper)


def validate_group_slice_args(args) -> None:
    """Validate deterministic group slicing arguments."""
    slice_index = args.group_slice_index
    slice_count = args.group_slice_count
    if slice_index is None and slice_count is None:
        return
    if slice_index is None or slice_count is None:
        raise ValueError("Both --group-slice-index and --group-slice-count must be specified")
    if slice_count <= 0:
        raise ValueError("--group-slice-count must be a positive integer")
    if slice_index < 0 or slice_index >= slice_count:
        raise ValueError("--group-slice-index must be in [0, --group-slice-count)")


def is_selected_test_case(test_case: TestCase, args) -> bool:
    """Return whether a test case matches the requested filters."""
    if len(args.runners) != 0 and test_case.runner_name not in args.runners:
        return False
    if len(args.presets) != 0 and test_case.preset_name not in args.presets:
        return False
    if len(args.forks) != 0 and test_case.fork_name not in args.forks:
        return False
    if len(args.cases) != 0 and not any(s in test_case.case_name for s in args.cases):
        return False
    return True


def select_generator_groups(
    input_test_groups: Iterable[TestGroup], args
) -> tuple[int, list[TestGroup]]:
    """Filter generator groups for execution."""
    total_found = 0
    selected_test_groups = []
    for test_group in input_test_groups:
        selected_group_cases = []
        for test_case in test_group.test_cases:
            total_found += 1
            if is_selected_test_case(test_case, args):
                selected_group_cases.append(test_case)

        if selected_group_cases:
            selected_test_groups.append(test_group)

    return total_found, selected_test_groups


def slice_generator_groups(selected_test_groups: list[TestGroup], args) -> list[TestGroup]:
    """Apply deterministic slicing to already-filtered generator groups."""
    return [
        test_group
        for group_index, test_group in enumerate(selected_test_groups)
        if group_index % args.group_slice_count == args.group_slice_index
    ]


def run_generator_groups(input_test_groups: Iterable[TestGroup], args=None):
    start_time = time.time()
    if args is None:
        args = parse_arguments()

    def debug_print(msg):
        """Only print if verbose is enabled."""
        if args.verbose:
            print(msg, flush=True)

    console = Console()
    dumper = Dumper()

    # Gracefully handle Ctrl+C
    install_sigint_handler(console)
    validate_group_slice_args(args)

    total_found, selected_test_groups = select_generator_groups(
        input_test_groups, args
    )
    if args.group_slice_count is not None:
        selected_test_groups = slice_generator_groups(selected_test_groups, args)

    selected_test_cases = []
    for test_group in selected_test_groups:
        for test_case in test_group.test_cases:
            # Set the output dir and add this to out list
            test_case.set_output_dir(args.output_dir)
            if test_case.dir.exists():
                shutil.rmtree(test_case.dir)
            selected_test_cases.append(test_case)

    if len(selected_test_cases) == 0:
        # Show summary even when all tests are filtered out
        elapsed = round(time.time() - start_time, 2)
        display_test_summary(console, total_found, 0, 0, 0, elapsed)
        return

    debug_print(f"Generating tests into {args.output_dir}")
    if args.group_slice_count is not None:
        debug_print(
            f"Selecting deterministic group slice "
            f"{args.group_slice_index + 1}/{args.group_slice_count} "
            f"({len(selected_test_groups)} groups)"
        )
    tests_prefix = get_shared_prefix(selected_test_cases)

    def worker_function(data):
        """Execute a test group and update active tests."""
        test_group, active_tests = data
        key = (uuid.uuid4(), test_group.get_identifier())
        test_start = time.time()
        active_tests[key] = test_start

        debug_print(f"Starting: {test_group.get_identifier()}")

        try:
            execute_test_group(test_group, dumper)
            elapsed = time.time() - test_start
            debug_print(f"Generated: {test_group.get_identifier()} (took {elapsed:.2f}s)")
            return ("generated", len(test_group.test_cases))
        except SkippedTest:
            elapsed = time.time() - test_start
            debug_print(f"Skipped: {test_group.get_identifier()} (took {elapsed:.2f}s)")
            return ("skipped", len(test_group.test_cases))
        finally:
            del active_tests[key]

    def periodic_status_print(active_tests, total_tasks, completed, skipped, interval=300):
        """Print status updates periodically in verbose mode."""
        process = psutil.Process()
        while completed.value < total_tasks:
            time.sleep(interval)
            remaining = total_tasks - completed.value
            if remaining > 0:
                active_count = len(active_tests)
                # Get system-wide and process memory stats
                vm = psutil.virtual_memory()
                total_memory_mb = vm.total / 1024 / 1024
                system_used_mb = vm.used / 1024 / 1024
                # Include main process + all child processes (worker pool)
                process_rss_mb = process.memory_info().rss / 1024 / 1024
                for child in process.children(recursive=True):
                    try:
                        process_rss_mb += child.memory_info().rss / 1024 / 1024
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                debug_print(
                    f"Progress: {completed.value}/{total_tasks} completed, "
                    f"{skipped.value} skipped, {active_count} active, "
                    f"{remaining} remaining, elapsed {time_since(start_time)}"
                )
                debug_print(
                    f"Memory: "
                    f"this process {process_rss_mb:.0f}MB, "
                    f"all processes {system_used_mb:.0f}MB, "
                    f"total available {total_memory_mb:.0f}MB"
                )
                if active_tests:
                    for key, start_time_test in list(active_tests.items()):
                        debug_print(
                            f"  - Active: {key[1]} (running for {time_since(start_time_test)})"
                        )

    def display_active_tests(active_tests, total_tasks, completed, skipped, width):
        """Display a table of active tests."""
        with Live(console=console) as live:
            while True:
                remaining = total_tasks - completed.value
                if remaining == 0:
                    # Show a final status when the queue is empty
                    # This is better than showing an empty table
                    text = Text.from_markup(f"Completed {tests_prefix} in {time_since(start_time)}")
                    live.update(text)
                    break

                info = ", ".join(
                    [
                        f"gen={tests_prefix}",
                        f"threads={args.threads}",
                        f"total={total_tasks}",
                        f"skipped={skipped.value}",
                        f"remaining={remaining}",
                        f"time={time_since(start_time)}",
                    ]
                )
                column_header = f"Test ({info})"
                width = max(width, len(column_header))

                table = Table(box=box.ROUNDED)
                table.add_column(column_header, style="cyan", no_wrap=True, width=width)
                table.add_column("Elapsed Time", justify="right", style="magenta")
                for k, start in sorted(active_tests.items(), key=lambda x: x[1]):
                    table.add_row(k[1], f"{time_since(start)}")
                live.update(table)
                time.sleep(0.25)

    # Generate all of the test cases
    try:
        with multiprocessing.Manager() as manager:
            active_tests = manager.dict()
            completed = manager.Value("i", 0)
            skipped = manager.Value("i", 0)
            width = max([len(group.get_identifier()) for group in selected_test_groups])

            if not args.verbose:
                display_thread = threading.Thread(
                    target=display_active_tests,
                    args=(active_tests, len(selected_test_cases), completed, skipped, width),
                    daemon=True,
                )
                display_thread.start()
            else:
                # Start periodic status printing in verbose mode
                status_thread = threading.Thread(
                    target=periodic_status_print,
                    args=(active_tests, len(selected_test_cases), completed, skipped),
                    daemon=True,
                )
                status_thread.start()

            # Map each selected group to a worker
            inputs = [(group, active_tests) for group in selected_test_groups]

            if args.threads == 1:
                for input in inputs:
                    result, nr_cases = worker_function(input)
                    if result == "skipped":
                        skipped.value += nr_cases
                    completed.value += nr_cases
            else:
                # Restart workers periodically to prevent memory accumulation
                pool = Pool(processes=args.threads, maxtasksperchild=100)
                try:
                    for result, nr_cases in pool.uimap(worker_function, inputs):
                        if result == "skipped":
                            skipped.value += nr_cases
                        completed.value += nr_cases
                except KeyboardInterrupt:
                    # Terminate pool immediately on interrupt
                    pool.terminate()
                    pool.join()
                    raise
                else:
                    # Normal cleanup when completed
                    pool.close()
                    pool.join()

            if not args.verbose:
                display_thread.join()

            elapsed = round(time.time() - start_time, 2)

            # Display final summary using rich
            total_selected = len(selected_test_cases)
            total_completed = completed.value - skipped.value
            total_skipped = skipped.value

        display_test_summary(
            console, total_found, total_selected, total_completed, total_skipped, elapsed
        )

        debug_print(f"Completed generation of {tests_prefix} in {elapsed} seconds")
    except KeyboardInterrupt:
        return
