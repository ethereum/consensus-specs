from importlib import reload
from typing import Iterable

from eth2spec.test.helpers.constants import ALTAIR, MINIMAL, MAINNET, PHASE0
from eth2spec.config import config_util
from eth2spec.test.altair.transition import test_transition as test_altair_transition
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.altair import spec as spec_altair

from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.gen_helpers.gen_from_tests.gen import generate_from_tests


def create_provider(tests_src, config_name: str, pre_fork_name: str, post_fork_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        reload(spec_phase0)
        reload(spec_altair)
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='transition',
            handler_name='core',
            src=tests_src,
            fork_name=post_fork_name,
            phase=pre_fork_name,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


TRANSITION_TESTS = ((PHASE0, ALTAIR, test_altair_transition),)


if __name__ == "__main__":
    for pre_fork, post_fork, transition_test_module in TRANSITION_TESTS:
        gen_runner.run_generator("transition", [
            create_provider(transition_test_module, MINIMAL, pre_fork, post_fork),
            create_provider(transition_test_module, MAINNET, pre_fork, post_fork),
        ])
