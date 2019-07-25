from typing import Callable, Iterable

from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.phase_0.epoch_processing import (
    test_process_crosslinks,
    test_process_final_updates,
    test_process_justification_and_finalization,
    test_process_registry_updates,
    test_process_slashings
)
from gen_base import gen_runner, gen_suite, gen_typing
from gen_from_tests.gen import generate_from_tests
from preset_loader import loader


def create_suite(handler_name: str, tests_src, config_name: str) \
        -> Callable[[str], gen_typing.TestProvider]:

    def prepare_fn(configs_path: str) -> str:
        presets = loader.load_presets(configs_path, config_name)
        spec_phase0.apply_constants_preset(presets)
        spec_phase1.apply_constants_preset(presets)
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name='epoch_processing',
            handler_name=handler_name,
            src=tests_src,
            fork_name='phase0'
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("epoch_processing", [
        create_suite('crosslinks', test_process_crosslinks, 'minimal'),
        create_suite('crosslinks', test_process_crosslinks, 'mainnet'),
        create_suite('final_updates', test_process_final_updates, 'minimal'),
        create_suite('final_updates', test_process_final_updates, 'mainnet'),
        create_suite('justification_and_finalization', test_process_justification_and_finalization, 'minimal'),
        create_suite('justification_and_finalization', test_process_justification_and_finalization, 'mainnet'),
        create_suite('registry_updates', test_process_registry_updates, 'minimal'),
        create_suite('registry_updates', test_process_registry_updates, 'mainnet'),
        create_suite('slashings', test_process_slashings, 'minimal'),
        create_suite('slashings', test_process_slashings, 'mainnet'),
    ])
