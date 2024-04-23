from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.specs import spec_targets
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestProvider
from itertools import product
from toolz.dicttoolz import merge
from typing import Iterable
from importlib import import_module
from eth2spec.utils import bls
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName
from minizinc import Instance, Model, Solver
from ruamel.yaml import YAML
from mutation_operators import mk_mutations, MutatorsGenerator
import random


BLS_ACTIVE = False
GENERATOR_NAME = 'fork_choice_generated'


forks = [ALTAIR]
presets = [MINIMAL]


def _import_block_tree_test_fn():
    src = import_module('eth2spec.test.phase0.fork_choice.test_sm_links_tree_model')
    print("generating test vectors from tests source: %s" % src.__name__)
    return getattr(src, 'test_sm_links_tree_model')


def _find_sm_link_solutions(anchor_epoch: int,
        number_of_epochs: int,
        number_of_links: int) -> Iterable[Iterable[tuple]]:
    # Dependencies:
    #   1. Install minizinc binary
    #      https://www.minizinc.org/doc-2.5.5/en/installation_detailed_linux.html
    #   2. Install minizinc python lib
    #      pip install minizinc
    #   3. Install and confifure gecode solver:
    #      https://www.minizinc.org/doc-2.5.5/en/installation_detailed_linux.html#gecode
    sm_links = Model('./model/minizinc/SM_links.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, sm_links)
    instance['AE'] = anchor_epoch  # anchor epoch
    instance['NE'] = number_of_epochs  # number of epochs, starting from AE
    instance['NL'] = number_of_links  # number of super-majority links

    solutions = instance.solve(all_solutions=True)
    for i in range(len(solutions)):
        yield {'sm_links': list(zip(solutions[i, 'sources'], solutions[i, 'targets']))}


def _find_block_tree_solutions(number_of_blocks: int,
                               max_children: int,
                               number_of_solutions: int) -> Iterable[dict]:
    model = Model('./model/minizinc/Block_tree.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, model)
    instance['NB'] = number_of_blocks
    instance['MC'] = max_children

    solutions = instance.solve(nr_solutions=number_of_solutions)
    return [{'block_parents': s.parent} for s in solutions]


def _load_block_tree_instances(instance_path: str) -> Iterable[dict]:
    yaml = YAML(typ='safe')
    solutions = yaml.load(open(instance_path, 'r'))
    return solutions


def _create_block_tree_providers(test_name: str, /,
        forks: Iterable[SpecForkName],
        presets: Iterable[PresetBaseName],
        debug: bool,
        initial_seed: int,
        solutions: Iterable,
        number_of_variations: int,
        number_of_mutations: int,
        with_attester_slashings: bool,
        with_invalid_messages: bool) -> Iterable[TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    def make_cases_fn() -> Iterable[TestCase]:
        _test_fn = _import_block_tree_test_fn()

        def test_fn(phase: str, preset: str, seed: int, sm_links, block_parents):
            return _test_fn(generator_mode=True,
                            phase=phase,
                            preset=preset,
                            bls_active=BLS_ACTIVE,
                            debug=debug,
                            seed=seed,
                            sm_links=sm_links,
                            block_parents=block_parents,
                            with_attester_slashings=with_attester_slashings,
                            with_invalid_messages=with_invalid_messages)

        seeds = [initial_seed]
        if number_of_variations > 1:
            rnd = random.Random(initial_seed)
            seeds = [rnd.randint(1, 10000) for _ in range(number_of_variations)]
            seeds[0] = initial_seed

        for i, solution in enumerate(solutions):
            for seed in seeds:
                for fork_name in forks:
                    for preset_name in presets:
                        spec = spec_targets[preset_name][fork_name]
                        mutation_generator = MutatorsGenerator(
                            spec, seed, number_of_mutations,
                            lambda: test_fn(fork_name, preset_name, seed,
                                            sm_links=solution['sm_links'], block_parents=solution['block_parents']),
                            debug=debug)
                        for j in range(1 + number_of_mutations):
                            yield TestCase(fork_name=fork_name,
                                        preset_name=preset_name,
                                        runner_name=GENERATOR_NAME,
                                        handler_name=test_name,
                                        suite_name='fork_choice',
                                        case_name=test_name + '_' + str(i) + '_' + str(seed) + '_' + str(j),
                                        case_fn=mutation_generator.next_test_case)

    yield TestProvider(prepare=prepare_fn, make_cases=make_cases_fn)


def _import_block_cover_test_fn():
    src = import_module('eth2spec.test.phase0.fork_choice.test_sm_links_tree_model')
    print("generating test vectors from tests source: %s" % src.__name__)
    return getattr(src, 'test_filter_block_tree_model')


def _find_block_cover_model_solutions(anchor_epoch: int,
                          store_justified_epoch_equal_zero: bool,
                          block_voting_source_epoch_equal_store_justified_epoch: bool,
                          block_voting_source_epoch_plus_two_greater_or_equal_current_epoch: bool,
                          block_is_leaf: bool,
                          nr_solutions: int=5) -> []:
    block_cover3 = Model('./model/minizinc/Block_cover3.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, block_cover3)
    instance['AE'] = anchor_epoch
    instance['store_je_eq_zero'] = store_justified_epoch_equal_zero
    instance['block_vse_eq_store_je'] = block_voting_source_epoch_equal_store_justified_epoch
    instance['block_vse_plus_two_ge_curr_e'] = block_voting_source_epoch_plus_two_greater_or_equal_current_epoch
    instance['block_is_leaf'] = block_is_leaf

    result = instance.solve(nr_solutions=nr_solutions)

    output = []
    for s in result.solution:
        max_block = s.max_block
        output.append({'block_epochs': s.es[:max_block + 1],
               'parents': s.parents[:max_block + 1],
               'previous_justifications': s.prevs[:max_block + 1],
               'current_justifications': s.currs[:max_block + 1],
               'current_epoch': s.curr_e,
               'store_justified_epoch': s.store_je,
               'target_block': s.target_block,
               'predicates': {
                   'store_je_eq_zero': store_justified_epoch_equal_zero,
                   'block_vse_eq_store_je': block_voting_source_epoch_equal_store_justified_epoch,
                   'block_vse_plus_two_ge_curr_e': block_voting_source_epoch_plus_two_greater_or_equal_current_epoch,
                   'block_is_leaf': block_is_leaf
               }})

    return output


def _generate_block_cover_model_solutions(anchor_epoch: int, nr_solutions: int=5, debug=False):
    solutions = []

    for store_je_eq_zero in [True, False]:
        for block_vse_eq_store_je in [True, False]:
            for block_vse_plus_two_ge_curr_e in [True, False]:
                for block_is_leaf in [True, False]:
                    if store_je_eq_zero and not block_vse_eq_store_je:
                        continue
                    if anchor_epoch == 0 and not store_je_eq_zero:
                        continue
                    results = _find_block_cover_model_solutions(
                                                    anchor_epoch=0 if store_je_eq_zero else anchor_epoch,
                                                    store_justified_epoch_equal_zero=store_je_eq_zero,
                                                    block_voting_source_epoch_equal_store_justified_epoch=block_vse_eq_store_je,
                                                    block_voting_source_epoch_plus_two_greater_or_equal_current_epoch=block_vse_plus_two_ge_curr_e,
                                                    block_is_leaf=block_is_leaf,
                                                    nr_solutions=nr_solutions)
                    if debug:
                        print('\n\n')
                        print(['store_je_eq_zero=' + str(store_je_eq_zero),
                                'block_vse_eq_store_je=' + str(block_vse_eq_store_je),
                                'block_vse_plus_two_ge_curr_e=' + str(block_vse_plus_two_ge_curr_e),
                                'block_is_leaf=' + str(block_is_leaf)])
                        for r in results:
                            print(r)

                    solutions.extend(results)
    
    return solutions


def _load_block_cover_instances(instance_path: str):
    yaml = YAML(typ='safe')
    solutions = yaml.load(open(instance_path, 'r'))
    return solutions


def _create_block_cover_providers(test_name: str, /,
        forks: Iterable[SpecForkName],
        presets: Iterable[PresetBaseName],
        debug: bool,
        initial_seed: int,
        solutions,
        number_of_variations: int,
        number_of_mutations: int) -> Iterable[TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    def make_cases_fn() -> Iterable[TestCase]:
        _test_fn = _import_block_cover_test_fn()
        def test_fn(phase: str, preset: str, seed: int, solution):
            return _test_fn(generator_mode=True,
                            phase=phase,
                            preset=preset,
                            bls_active=BLS_ACTIVE,
                            debug=debug,
                            seed=seed,
                            model_params=solution)

        seeds = [initial_seed]
        if number_of_variations > 1:
            rnd = random.Random(initial_seed)
            seeds = [rnd.randint(1, 10000) for _ in range(number_of_variations)]
            seeds[0] = initial_seed

        for i, solution in enumerate(solutions):
            for seed in seeds:
                for fork_name in forks:
                    for preset_name in presets:
                        spec = spec_targets[preset_name][fork_name]
                        mutation_generator = MutatorsGenerator(
                            spec, seed, number_of_mutations,
                            lambda: test_fn(fork_name, preset_name, seed, solution),
                            debug=debug)
                        for j in range(1 + number_of_mutations):
                            yield TestCase(fork_name=fork_name,
                                        preset_name=preset_name,
                                        runner_name=GENERATOR_NAME,
                                        handler_name=test_name,
                                        suite_name='fork_choice',
                                        case_name=test_name + '_' + str(i) + '_' + str(seed) + '_' + str(j),
                                        case_fn=mutation_generator.next_test_case)

    yield TestProvider(prepare=prepare_fn, make_cases=make_cases_fn)


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
        '--fc-gen-test-kind',
        dest='fc_gen_test_kind',
        type=str,
        required=True,
        help='Test kind: block_tree or block_cover'
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
    arg_parser.add_argument(
        '--fc-gen-epochs',
        dest='fc_gen_epochs',
        default=2,
        type=int,
        required=False,
        help='Number of epochs beyond the anchor epoch'
    )
    arg_parser.add_argument(
        '--fc-gen-links',
        dest='fc_gen_links',
        default=1,
        type=int,
        required=False,
        help='Number of super majority links per solution'
    )
    arg_parser.add_argument(
        '--fc-gen-mutations',
        dest='fc_gen_mutations',
        default=0,
        type=int,
        required=False,
        help='Number of mutations per base test case'
    )
    arg_parser.add_argument(
        '--fc-gen-attester-slashings',
        dest='fc_gen_attester_slashings',
        default=False,
        type=bool,
        required=False,
        help='Pass with_attester_slashings flag'
    )
    arg_parser.add_argument(
        '--fc-gen-invalid-messages',
        dest='fc_gen_invalid_messages',
        default=False,
        type=bool,
        required=False,
        help='Pass with_invalid_messages flag'
    )
    arg_parser.add_argument(
        '--fc-gen-instances-path',
        dest='fc_gen_instances_path',
        default=None,
        type=str,
        required=False,
        help='Path to a file with pre-generated instances'
    )
    arg_parser.add_argument(
        '--fc-gen-nr-solutions',
        dest='fc_gen_nr_solutions',
        default=5,
        type=int,
        required=False,
        help='Number of solutions per MiniZinc query'
    )

    args = arg_parser.parse_args()

    if args.fc_gen_test_kind == 'block_tree':
        if args.fc_gen_instances_path is not None:
            solutions = _load_block_tree_instances(args.fc_gen_instances_path)
        else:
            sm_link_solutions = _find_sm_link_solutions(args.fc_gen_anchor_epoch, args.fc_gen_epochs, args.fc_gen_links)
            block_tree_solutions = _find_block_tree_solutions(16, 3, 3)
            solutions = [merge(*sols) for sols in product(sm_link_solutions, block_tree_solutions)]
        
        if not args.fc_gen_attester_slashings and not args.fc_gen_invalid_messages:
            test_name = 'block_tree'
        elif args.fc_gen_attester_slashings and not args.fc_gen_invalid_messages:
            test_name = 'attester_slashings'
        elif args.fc_gen_invalid_messages and not args.fc_gen_attester_slashings:
            test_name = 'invalid_messages'
        else:
            test_name = 'attester_slashings_and_invalid_messages'

        gen_runner.run_generator(GENERATOR_NAME,
                                _create_block_tree_providers(test_name,
                                                forks=forks,
                                                presets=presets,
                                                debug=args.fc_gen_debug,
                                                initial_seed=args.fc_gen_seed,
                                                solutions=solutions,
                                                number_of_variations=args.fc_gen_variations,
                                                number_of_mutations=args.fc_gen_mutations,
                                                with_attester_slashings=args.fc_gen_attester_slashings,
                                                with_invalid_messages=args.fc_gen_invalid_messages),
                                arg_parser)
    elif args.fc_gen_test_kind == 'block_cover':
        if args.fc_gen_instances_path is not None:
            solutions = _load_block_cover_instances(args.fc_gen_instances_path)
        else:
            solutions = _generate_block_cover_model_solutions(args.fc_gen_anchor_epoch, args.fc_gen_nr_solutions, args.fc_gen_debug)

        test_name = 'block_cover'
        gen_runner.run_generator(GENERATOR_NAME,
                                _create_block_cover_providers(
                                                test_name,
                                                forks=forks,
                                                presets=presets,
                                                debug=args.fc_gen_debug,
                                                initial_seed=args.fc_gen_seed,
                                                solutions=solutions,
                                                number_of_variations=args.fc_gen_variations,
                                                number_of_mutations=args.fc_gen_mutations),
                                arg_parser)
    else:
        raise ValueError(f'Unsupported test kind: {args.fc_gen_test_kind}')
