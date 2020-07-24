from typing import Iterable

from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.phase0.rewards import (
    test_basic,
    test_leak,
    test_random,
)
from gen_base import gen_runner, gen_typing
from gen_from_tests.gen import generate_from_tests
from importlib import reload
from eth2spec.config import config_util
from eth2spec.test.context import PHASE0
from eth2spec.utils import bls


def create_provider(tests_src, config_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        reload(spec_phase0)
        reload(spec_phase1)
        bls.use_milagro()
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='rewards',
            handler_name='core',
            src=tests_src,
            fork_name=PHASE0,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("rewards", [
        create_provider(test_basic, 'minimal'),
        create_provider(test_basic, 'mainnet'),
        create_provider(test_leak, 'minimal'),
        create_provider(test_leak, 'mainnet'),
        create_provider(test_random, 'minimal'),
        create_provider(test_random, 'mainnet'),
    ])
