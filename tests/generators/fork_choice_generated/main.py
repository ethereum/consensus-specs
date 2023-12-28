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


def _create_providers(forks: Iterable[SpecForkName],
        presets: Iterable[PresetBaseName],
        debug: bool,
        initial_seed: int,
        anchor_epoch: int,
        number_of_epochs: int,
        number_of_links: int,
        number_of_variations: int) -> Iterable[TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    def make_cases_fn() -> Iterable[TestCase]:
        test_fn = _import_test_fn()
        solutions = _find_sm_link_solutions(anchor_epoch, number_of_epochs, number_of_links)

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
                                       runner_name='fork_choice_generated',
                                       handler_name='sm_links_tree_model',
                                       suite_name='fork_choice',
                                       case_name='sm_links_tree_model_' + str(i) + '_' + str(seed),
                                       case_fn=lambda: test_fn(generator_mode=True,
                                                               phase=fork_name,
                                                               preset=preset_name,
                                                               bls_active=BLS_ACTIVE,
                                                               debug=debug,
                                                               seed=seed,
                                                               sm_links=solution))

    yield TestProvider(prepare=prepare_fn, make_cases=make_cases_fn)


if __name__ == "__main__":
    anchor_epoch = 2
    number_of_epochs = 2
    number_of_links = 1
    debug = True
    initial_seed = 9326
    number_of_variations = 1

    forks = [ALTAIR]
    presets = [MINIMAL]

    gen_runner.run_generator('fork_choice_generated', _create_providers(forks=forks,
                                                                        presets=presets,
                                                                        debug=debug,
                                                                        initial_seed=initial_seed,
                                                                        anchor_epoch=anchor_epoch,
                                                                        number_of_epochs=number_of_epochs,
                                                                        number_of_links=number_of_links,
                                                                        number_of_variations=number_of_variations))
