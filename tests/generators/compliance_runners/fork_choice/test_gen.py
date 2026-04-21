import argparse
import os
import warnings

import pytest

DEFAULT_OUTPUT_DIR = "comptests"


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test_gen",
        description="Legacy compatibility wrapper for compliance test generation.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory into which the generated test files will be dumped.",
    )
    parser.add_argument(
        "--presets",
        dest="presets",
        nargs="*",
        type=str,
        default=[],
        required=False,
        help="Specify presets to run with. Allows defaults if none are specified.",
    )
    parser.add_argument(
        "--forks",
        dest="forks",
        nargs="*",
        type=str,
        default=[],
        required=False,
        help="Specify forks to run with. Allows defaults if none are specified.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=os.cpu_count(),
        help="Generate tests with N threads. Defaults to core count.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print more information to the console.",
    )

    parser.add_argument(
        "--fc-gen-debug",
        dest="fc_gen_debug",
        action="store_true",
        default=False,
        required=False,
        help="If set provides debug output and enable additional checks for generated chains",
    )
    parser.add_argument(
        "--fc-gen-config",
        dest="fc_gen_config",
        type=str,
        required=False,
        choices=["tiny", "small", "standard"],
        help="Name of test generator configuration: tiny, small or standard",
    )
    parser.add_argument(
        "--fc-gen-config-path",
        dest="fc_gen_config_path",
        type=str,
        required=False,
        help="Path to a file with test generator configurations",
    )
    parser.add_argument(
        "--fc-gen-multi-processing",
        dest="fc_gen_multi_processing",
        action="store_true",
        default=False,
        required=False,
        help="If set generates tests in the multi-processing mode",
    )
    parser.add_argument(
        "--fc-gen-seed",
        dest="fc_gen_seed",
        type=int,
        default=None,
        required=False,
        help="override test seeds (fuzzing mode)",
    )

    return parser


def _build_pytest_args(args: argparse.Namespace) -> list[str]:
    pytest_args = [
        "--comptests-output",
        args.output_dir,
    ]

    if args.fc_gen_config is not None:
        pytest_args.extend(["--fc-gen-config", args.fc_gen_config])
    if args.fc_gen_config_path is not None:
        pytest_args.extend(["--fc-gen-config-path", args.fc_gen_config_path])
    if args.fc_gen_debug:
        pytest_args.append("--fc-gen-debug")
    if args.fc_gen_seed is not None:
        pytest_args.extend(["--fc-gen-seed", str(args.fc_gen_seed)])
    if args.verbose:
        pytest_args.append("-v")
    if args.forks:
        for fork in args.forks:
            pytest_args.extend(["--forks", fork])
    if args.presets:
        for preset in args.presets:
            pytest_args.extend(["--presets", preset])

    if args.fc_gen_multi_processing or args.threads != 1:
        worker_count = "logical" if args.threads is None else str(args.threads)
        pytest_args.extend(["-n", worker_count, "--dist=worksteal"])

    pytest_args.append(__file__.replace("test_gen.py", "generate_comptests.py"))
    return pytest_args


def main():
    warnings.warn(
        "test_gen.py is deprecated; use `make comptests` instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    args = create_arg_parser().parse_args()
    raise SystemExit(pytest.main(_build_pytest_args(args)))


if __name__ == "__main__":
    main()
