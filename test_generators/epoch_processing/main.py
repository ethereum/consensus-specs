from typing import Callable, Iterable

from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.phase_0.epoch_processing import (
    test_process_crosslinks,
    test_process_registry_updates
)
from gen_base import gen_runner, gen_suite, gen_typing
from gen_from_tests.gen import generate_from_tests
from preset_loader import loader


def create_suite(transition_name: str, config_name: str, get_cases: Callable[[], Iterable[gen_typing.TestCase]]) \
        -> Callable[[str], gen_typing.TestSuiteOutput]:
    def suite_definition(configs_path: str) -> gen_typing.TestSuiteOutput:
        presets = loader.load_presets(configs_path, config_name)
        spec_phase0.apply_constants_preset(presets)
        spec_phase1.apply_constants_preset(presets)

        return ("%s_%s" % (transition_name, config_name), transition_name, gen_suite.render_suite(
            title="%s epoch processing" % transition_name,
            summary="Test suite for %s type epoch processing" % transition_name,
            forks_timeline="testing",
            forks=["phase0"],
            config=config_name,
            runner="epoch_processing",
            handler=transition_name,
            test_cases=get_cases()))

    return suite_definition


if __name__ == "__main__":
    gen_runner.run_generator("epoch_processing", [
        create_suite('crosslinks', 'minimal', lambda: generate_from_tests(test_process_crosslinks, 'phase0')),
        create_suite('crosslinks', 'mainnet', lambda: generate_from_tests(test_process_crosslinks, 'phase0')),
        create_suite('registry_updates', 'minimal', lambda: generate_from_tests(test_process_registry_updates, 'phase0')),
        create_suite('registry_updates', 'mainnet', lambda: generate_from_tests(test_process_registry_updates, 'phase0')),
    ])
