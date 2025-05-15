import argparse
import os
import pathlib


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="generator",
        description=f"Generate YAML test suite files.",
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
        "--runners",
        dest="runners",
        nargs="*",
        type=str,
        default=[],
        required=False,
        help="Specify runners to run with. Allows all if no runner names are specified.",
    )
    parser.add_argument(
        "--presets",
        dest="presets",
        nargs="*",
        type=str,
        default=[],
        required=False,
        help="Specify presets to run with. Allows all if no preset names are specified.",
    )
    parser.add_argument(
        "--forks",
        dest="forks",
        nargs="*",
        type=str,
        default=[],
        required=False,
        help="Specify forks to run with. Allows all if no fork names are specified.",
    )
    parser.add_argument(
        "--cases",
        dest="cases",
        nargs="*",
        type=str,
        default=[],
        required=False,
        help="Specify test cases to run with. Allows all if no test case names are specified.",
    )
    parser.add_argument(
        "--modcheck",
        action="store_true",
        default=False,
        help="Check generator modules, do not run any tests.",
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
        help="Generate tests with N threads. Defaults to core count.",
    )
    return parser.parse_args()
