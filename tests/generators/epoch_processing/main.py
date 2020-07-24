from typing import Iterable

from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.phase0.epoch_processing import (
    test_process_final_updates,
    test_process_justification_and_finalization,
    test_process_registry_updates,
    test_process_rewards_and_penalties,
    test_process_slashings
)
from gen_base import gen_runner, gen_typing
from gen_from_tests.gen import generate_from_tests
from importlib import reload
from eth2spec.config import config_util
from eth2spec.test.context import PHASE0
from eth2spec.utils import bls


def create_provider(handler_name: str, tests_src, config_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        config_util.prepare_config(configs_path, config_name)
        reload(spec_phase0)
        reload(spec_phase1)
        bls.use_milagro()
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='epoch_processing',
            handler_name=handler_name,
            src=tests_src,
            fork_name=PHASE0,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("epoch_processing", [
        create_provider('final_updates', test_process_final_updates, 'minimal'),
        create_provider('final_updates', test_process_final_updates, 'mainnet'),
        create_provider('justification_and_finalization', test_process_justification_and_finalization, 'minimal'),
        create_provider('justification_and_finalization', test_process_justification_and_finalization, 'mainnet'),
        create_provider('registry_updates', test_process_registry_updates, 'minimal'),
        create_provider('registry_updates', test_process_registry_updates, 'mainnet'),
        create_provider('rewards_and_penalties', test_process_rewards_and_penalties, 'minimal'),
        # runs full epochs filled with data, with uncached ssz. Disabled for now.
        # create_provider('rewards_and_penalties', test_process_rewards_and_penalties, 'mainnet'),
        create_provider('slashings', test_process_slashings, 'minimal'),
        create_provider('slashings', test_process_slashings, 'mainnet'),
    ])
