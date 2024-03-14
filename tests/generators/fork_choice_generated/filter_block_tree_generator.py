from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestProvider
from typing import Iterable
from importlib import import_module
from eth2spec.utils import bls
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName
from minizinc import Instance, Model, Solver
import random

BLS_ACTIVE = False
GENERATOR_NAME = 'filter_block_tree'


def _import_test_fn():
    src = import_module('eth2spec.test.phase0.fork_choice.test_sm_links_tree_model')
    print("generating test vectors from tests source: %s" % src.__name__)
    return getattr(src, 'test_filter_block_tree_model')


def _find_model_solutions(anchor_epoch: int,
                          store_justified_epoch_equal_zero: bool,
                          block_voting_source_epoch_equal_store_justified_epoch: bool,
                          block_voting_source_epoch_plus_two_greater_or_equal_current_epoch: bool,
                          block_is_leaf: bool,
                          block_is_justified_root_descendant: bool) -> Iterable[Iterable[tuple]]:
    block_cover3 = Model('./model/minizinc/Block_cover3.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, block_cover3)
    instance['AE'] = anchor_epoch
    instance['store_je_eq_zero'] = store_justified_epoch_equal_zero
    instance['block_vse_eq_store_je'] = block_voting_source_epoch_equal_store_justified_epoch
    instance['block_vse_plus_two_ge_curr_e'] = block_voting_source_epoch_plus_two_greater_or_equal_current_epoch
    instance['block_is_leaf'] = block_is_leaf
    instance['block_is_justified_descendant'] = block_is_justified_root_descendant

    result = instance.solve(nr_solutions=5)

    for s in result.solution:
        max_block = s.max_block
        yield {'block_epochs': s.es[:max_block + 1],
               'ancestors': s.ancestors[:max_block + 1],
               'previous_justifications': s.prevs[:max_block + 1],
               'current_justifications': s.currs[:max_block + 1],
               'current_epoch': s.curr_e,
               'store_justified_epoch': s.store_je,
               'target_block': s.target_block}


def _create_providers(forks: Iterable[SpecForkName],
        presets: Iterable[PresetBaseName],
        debug: bool,
        initial_seed: int,
        anchor_epoch: int,
        number_of_variations: int) -> Iterable[TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    def make_cases_fn() -> Iterable[TestCase]:
        test_fn = _import_test_fn()

        seeds = [initial_seed]
        if number_of_variations > 1:
            rnd = random.Random(initial_seed)
            seeds = [rnd.randint(1, 10000) for _ in range(number_of_variations)]
            seeds[0] = initial_seed

        solutions = _find_model_solutions(anchor_epoch=anchor_epoch,
                                          store_justified_epoch_equal_zero=False,
                                          block_voting_source_epoch_equal_store_justified_epoch=False,
                                          block_voting_source_epoch_plus_two_greater_or_equal_current_epoch=True,
                                          block_is_leaf=True,
                                          block_is_justified_root_descendant=True)

        for i, solution in enumerate(solutions):
            for seed in seeds:
                for fork_name in forks:
                    for preset_name in presets:
                        yield TestCase(fork_name=fork_name,
                                       preset_name=preset_name,
                                       runner_name=GENERATOR_NAME,
                                       handler_name='filter_block_tree_model',
                                       suite_name='fork_choice',
                                       case_name='filter_block_tree_model_' + str(i) + '_' + str(seed),
                                       case_fn=lambda: test_fn(generator_mode=True,
                                                               phase=fork_name,
                                                               preset=preset_name,
                                                               bls_active=BLS_ACTIVE,
                                                               debug=debug,
                                                               seed=seed,
                                                               model_params=solution))

    yield TestProvider(prepare=prepare_fn, make_cases=make_cases_fn)


if __name__ == "__main__":
    forks = [ALTAIR]
    presets = [MINIMAL]

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
        '--fc-gen-seed',
        dest='fc_gen_seed',
        default=1,
        type=int,
        required=False,
        help='Provides randomizer with initial seed'
    )
    arg_parser.add_argument(
        '--fc-gen-variations',
        dest='fc_gen_variations',
        default=1,
        type=int,
        required=False,
        help='Number of random variations per each solution'
    )
    arg_parser.add_argument(
        '--fc-gen-anchor-epoch',
        dest='fc_gen_anchor_epoch',
        default=0,
        type=int,
        required=False,
        help='Anchor epoch'
    )

    args = arg_parser.parse_args()

    gen_runner.run_generator(GENERATOR_NAME,
                             _create_providers(forks=forks,
                                               presets=presets,
                                               debug=args.fc_gen_debug,
                                               initial_seed=args.fc_gen_seed,
                                               anchor_epoch=args.fc_gen_anchor_epoch,
                                               number_of_variations=args.fc_gen_variations),
                             arg_parser)
