from eth2spec.gen_helpers.gen_base import gen_runner

from filter_block_tree_generator import (
    forks as block_cover_forks,
    presets as block_cover_presets,
    _load_model_solutions as block_cover_load_solutions,
    _create_providers as block_cover_create_providers
)
from main import (
    forks as block_tree_forks,
    presets as block_tree_presets,
    _load_sm_link_solutions as block_tree_load_solutions,
    _create_providers as block_tree_create_providers
)


GENERATOR_NAME = 'fork_choice_generated'


test_gen_config = {
    'block_tree_test': {
        'test_type': 'block_tree',
        'instances': 'block_tree.yaml',
        'seed': 123,
        'nr_variations': 1,
        'nr_mutations': 0,
    },
    'invalid_message_test': {
        'test_type': 'block_tree',
        'with_invalid_messages': True,
        'instances': 'block_tree.yaml',
        'seed': 123,
        'nr_variations': 1,
        'nr_mutations': 1,
    },
    'attester_slashing_test': {
        'test_type': 'block_tree',
        'with_attester_slashings': True,
        'instances': 'block_tree.yaml',
        'seed': 123,
        'nr_variations': 1,
        'nr_mutations': 1,
    },
    'block_cover_test': {
        'test_type': 'block_cover',
        'instances': 'block_cover.yaml',
        'seed': 456,
        'nr_variations': 1,
        'nr_mutations': 0,
    }
}

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
    # TODO: load test_gen_config from a yaml file
    # arg_parser.add_argument(
    #     '--fc-gen-config',
    #     dest='fc_gen_config',
    #     type=str,
    #     default=None,
    #     required=False,
    #     help='Path to a file with test generator configurations'
    # )

    args = arg_parser.parse_args()

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
            sm_link_solutions = block_tree_load_solutions(instances_path)
            block_tree_solutions = [[0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]]
            providers = block_tree_create_providers(test_name,
                                                    forks=block_tree_forks,
                                                    presets=block_tree_presets,
                                                    debug=args.fc_gen_debug,
                                                    initial_seed=initial_seed,
                                                    sm_link_solutions=sm_link_solutions,
                                                    block_tree_solutions=block_tree_solutions,
                                                    number_of_variations=nr_variations,
                                                    number_of_mutations=nr_mutations,
                                                    with_attester_slashings=with_attester_slashings,
                                                    with_invalid_messages=with_invalid_messages)
        elif test_type == 'block_cover':
            solutions = block_cover_load_solutions(instances_path)
            providers = block_cover_create_providers(test_name,
                                                     forks=block_cover_forks,
                                                     presets=block_cover_presets,
                                                     debug=args.fc_gen_debug,
                                                     initial_seed=initial_seed,
                                                     solutions=solutions,
                                                     number_of_variations=nr_variations,
                                                     number_of_mutations=nr_mutations)
        else:
            raise ValueError(f'Unsupported test type: {test_type}')
        
        gen_runner.run_generator(GENERATOR_NAME, providers, arg_parser)


