"""
Test generator for eth/v1/config/spec beacon API endpoint.

Generates expected key-value pairs that clients must return from the
``/eth/v1/config/spec`` endpoint for each (preset, fork) combination.
"""

from eth_consensus_specs.test import context
from eth_consensus_specs.test.helpers.constants import ALL_PRESETS, TESTGEN_FORKS
from tests.generators.compliance_runners.gen_base import gen_runner
from tests.generators.compliance_runners.gen_base.args import create_arg_parser

context.is_pytest = False
context.is_generator = True

from .generate import enumerate_test_cases  # noqa: E402


def main():
    arg_parser = create_arg_parser()
    args = arg_parser.parse_args()

    forks = list(TESTGEN_FORKS) if not args.forks else args.forks
    presets = list(ALL_PRESETS) if not args.presets else args.presets

    test_cases = enumerate_test_cases(forks, presets)
    gen_runner.run_generator(test_cases, args)


if __name__ == "__main__":
    main()
