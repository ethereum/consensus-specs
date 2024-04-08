from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.gen_helpers.gen_base import gen_runner
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestProvider
from typing import Iterable
from importlib import import_module
from eth2spec.utils import bls
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName
from minizinc import Instance, Model, Solver
from ruamel.yaml import YAML
import random


yaml = YAML(typ='safe')


BLS_ACTIVE = False
GENERATOR_NAME = 'fork_choice_generated'


forks = [ALTAIR]
presets = [MINIMAL]


def _import_test_fn():
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
        yield [_ for _ in zip(solutions[i, 'sources'], solutions[i, 'targets'])]


def _load_sm_link_solutions(instance_path: str) -> Iterable[Iterable[tuple]]:
    solutions = yaml.load(open(instance_path, 'r'))
    print('solutions', solutions)
    for solution in solutions:
        yield list(zip(solution['sources'], solution['targets']))


def _create_providers(forks: Iterable[SpecForkName],
        presets: Iterable[PresetBaseName],
        debug: bool,
        initial_seed: int,
        solutions: Iterable[Iterable[tuple]],
        number_of_variations: int,
        with_attester_slashings: bool,
        with_invalid_messages: bool) -> Iterable[TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    def make_cases_fn() -> Iterable[TestCase]:
        test_fn = _import_test_fn()
        # solutions = _find_sm_link_solutions(anchor_epoch, number_of_epochs, number_of_links)

        seeds = [initial_seed]
        if number_of_variations > 1:
            rnd = random.Random(initial_seed)
            seeds = [rnd.randint(1, 10000) for _ in range(number_of_variations)]
            seeds[0] = initial_seed

        for i, solution in enumerate(solutions):
            for seed in seeds:
                for fork_name in forks:
                    for preset_name in presets:
                        yield TestCase(fork_name=fork_name,
                                       preset_name=preset_name,
                                       runner_name=GENERATOR_NAME,
                                       handler_name='sm_links_tree_model',
                                       suite_name='fork_choice',
                                       case_name='sm_links_tree_model_' + str(i) + '_' + str(seed),
                                       case_fn=lambda: test_fn(generator_mode=True,
                                                               phase=fork_name,
                                                               preset=preset_name,
                                                               bls_active=BLS_ACTIVE,
                                                               debug=debug,
                                                               seed=seed,
                                                               sm_links=solution,
                                                               with_attester_slashings=with_attester_slashings,
                                                               with_invalid_messages=with_invalid_messages))

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
        '--fc-gen-instances-path',
        dest='fc_gen_instances_path',
        default=None,
        type=str,
        required=False,
        help='Path to a file with pre-generated instances'
    )

    args = arg_parser.parse_args()

    if args.fc_gen_instances_path is not None:
        solutions = _load_sm_link_solutions(args.fc_gen_instances_path)
    else:
        solutions = _find_sm_link_solutions(args.fc_gen_anchor_epoch, args.fc_gen_epochs, args.fc_gen_links)

    gen_runner.run_generator(GENERATOR_NAME,
                             _create_providers(forks=forks,
                                               presets=presets,
                                               debug=args.fc_gen_debug,
                                               initial_seed=args.fc_gen_seed,
                                               solutions=solutions,
                                               number_of_variations=args.fc_gen_variations,
                                               with_attester_slashings=True,
                                               with_invalid_messages=True),
                             arg_parser)
