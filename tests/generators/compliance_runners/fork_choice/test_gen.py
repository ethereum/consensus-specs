from instantiators.test_case import enumerate_test_cases, prepare_bls
from ruamel.yaml import YAML

from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.gen_helpers.gen_base.args import create_arg_parser
from eth2spec.test.helpers.constants import ELECTRA, MINIMAL

forks = [ELECTRA]
presets = [MINIMAL]


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
        required=True,
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

    # change default value for `threads` to detect whether it is explicitly set
    default_threads = arg_parser.get_default("threads")
    arg_parser.set_defaults(threads=0)

    args = arg_parser.parse_args()

    with open(args.fc_gen_config) as f:
        yaml = YAML(typ="safe")
        test_gen_config = yaml.load(f)

    if args.fc_gen_multi_processing or args.threads != 0:
        if args.threads == 0:
            args.threads = default_threads
        print("generating tests in multi-processing mode")
    else:
        args.threads = 1
        print("generating tests in single process mode")

    prepare_bls()
    test_cases = enumerate_test_cases(test_gen_config, forks, presets, args.fc_gen_debug)
    gen_runner.run_generator(test_cases, args)


if __name__ == "__main__":
    main()
