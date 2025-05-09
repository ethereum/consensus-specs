import argparse
import os
import pathlib


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
        type=pathlib.Path,
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
