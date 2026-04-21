from os import path

from eth_consensus_specs.test import context
from eth_consensus_specs.test.helpers.constants import ELECTRA, MINIMAL
from tests.generators.compliance_runners.gen_base import gen_runner
from tests.generators.compliance_runners.gen_base.args import create_arg_parser

context.is_pytest = False
context.is_generator = True

from .instantiators.test_case import enumerate_test_groups, prepare_bls  # noqa: E402

default_forks = [ELECTRA]
default_presets = [MINIMAL]


def main():
    arg_parser = create_arg_parser()

    arg_parser.add_argument(
        "--fc-gen-debug",
        dest="fc_gen_debug",
        action="store_true",
        default=False,
        required=False,
        help="If set provides debug output and enable additional checks for generated chains",
    )
    arg_parser.add_argument(
        "--fc-gen-config",
        dest="fc_gen_config",
        type=str,
        required=False,
        choices=["tiny", "small", "standard"],
        help="Name of test generator configuration: tiny, small or standard",
    )
    arg_parser.add_argument(
        "--fc-gen-config-path",
        dest="fc_gen_config_path",
        type=str,
        required=False,
        help="Path to a file with test generator configurations",
    )
    arg_parser.add_argument(
        "--fc-gen-multi-processing",
        dest="fc_gen_multi_processing",
        action="store_true",
        default=False,
        required=False,
        help="If set generates tests in the multi-processing mode",
    )
    arg_parser.add_argument(
        "--fc-gen-seed",
        dest="fc_gen_seed",
        type=int,
        default=None,
        required=False,
        help="override test seeds (fuzzing mode)",
    )

    # change default value for `threads` to detect whether it is explicitly set
    default_threads = arg_parser.get_default("threads")
    arg_parser.set_defaults(threads=0)

    args = arg_parser.parse_args()

    if args.fc_gen_multi_processing or args.threads != 0:
        if args.threads == 0:
            args.threads = default_threads
        print("generating tests in multi-processing mode")
    else:
        args.threads = 1
        print("generating tests in single process mode")

    forks = default_forks if args.forks == [] else args.forks
    presets = default_presets if args.presets == [] else args.presets

    if args.fc_gen_config_path is not None:
        config_path = args.fc_gen_config_path
    elif args.fc_gen_config is not None:
        config_path = path.join(path.dirname(__file__), args.fc_gen_config, "test_gen.yaml")
    else:
        raise ValueError("Neither neither fc-gen-config not fc-gen-config-path specified")

    prepare_bls()
    test_groups = enumerate_test_groups(
        config_path, forks, presets, args.fc_gen_debug, args.fc_gen_seed
    )
    gen_runner.run_generator_groups(test_groups, args)


if __name__ == "__main__":
    main()
