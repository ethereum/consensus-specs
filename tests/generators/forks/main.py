from importlib import reload
from typing import Iterable

from eth2spec.test.context import PHASE0, ALTAIR, MINIMAL, MAINNET
from eth2spec.config import config_util
from eth2spec.test.altair.fork import test_fork as test_altair_forks
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.altair import spec as spec_altair

from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.gen_helpers.gen_from_tests.gen import generate_from_tests


def create_provider(tests_src, config_name: str, phase: str, fork_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        reload(spec_phase0)
        reload(spec_altair)
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='fork',
            handler_name='fork',
            src=tests_src,
            fork_name=fork_name,
            phase=phase,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("forks", [
        create_provider(test_altair_forks, MINIMAL, PHASE0, ALTAIR),
        create_provider(test_altair_forks, MAINNET, PHASE0, ALTAIR),
    ])
