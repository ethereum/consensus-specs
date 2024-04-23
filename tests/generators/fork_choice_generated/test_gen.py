from eth2spec.gen_helpers.gen_base import gen_runner
from ruamel.yaml import YAML

from instance_generator import (
    forks,
    presets,
    _load_block_tree_instances,
    _create_block_tree_providers,
    _load_block_cover_instances,
    _create_block_cover_providers
)


yaml = YAML(typ='safe')


GENERATOR_NAME = 'fork_choice_generated'


if __name__ == "__main__":
    arg_parser = gen_runner.create_arg_parser(GENERATOR_NAME)

    arg_parser.add_argument(
        '--fc-gen-debug',
        dest='fc_gen_debug',
        action='store_true',
        default=False,
        required=False,
        help='If set provides debug output and enable additional checks for generated chains',
    )
    arg_parser.add_argument(
        '--fc-gen-config',
        dest='fc_gen_config',
        type=str,
        required=True,
        help='Path to a file with test generator configurations'
    )

    args = arg_parser.parse_args()

    with open(args.fc_gen_config, 'r') as f:
        test_gen_config = yaml.load(f)
    
    for test_name, params in test_gen_config.items():
        print(test_name)
        test_type = params['test_type']
        instances_path = params['instances']
        initial_seed = params['seed']
        nr_variations = params['nr_variations']
        nr_mutations = params['nr_mutations']
        with_attester_slashings = params.get('with_attester_slashings', False)
        with_invalid_messages = params.get('with_invalid_messages', False)

        if test_type == 'block_tree':
            solutions = _load_block_tree_instances(instances_path)
            providers = _create_block_tree_providers(test_name,
                                                    forks=forks,
                                                    presets=presets,
                                                    debug=args.fc_gen_debug,
                                                    initial_seed=initial_seed,
                                                    solutions=solutions,
                                                    number_of_variations=nr_variations,
                                                    number_of_mutations=nr_mutations,
                                                    with_attester_slashings=with_attester_slashings,
                                                    with_invalid_messages=with_invalid_messages)
        elif test_type == 'block_cover':
            solutions = _load_block_cover_instances(instances_path)
            providers = _create_block_cover_providers(test_name,
                                                     forks=forks,
                                                     presets=presets,
                                                     debug=args.fc_gen_debug,
                                                     initial_seed=initial_seed,
                                                     solutions=solutions,
                                                     number_of_variations=nr_variations,
                                                     number_of_mutations=nr_mutations)
        else:
            raise ValueError(f'Unsupported test type: {test_type}')
        
        gen_runner.run_generator(GENERATOR_NAME, providers, arg_parser)


