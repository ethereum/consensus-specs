from typing import Callable, Iterable

from eth2spec.test.block_processing import (
    test_process_attestation,
    test_process_attester_slashing,
    test_process_block_header,
    test_process_deposit,
    test_process_proposer_slashing,
    test_process_transfer,
    test_process_voluntary_exit
)

from gen_base import gen_runner, gen_suite, gen_typing
from gen_from_tests.gen import generate_from_tests
from preset_loader import loader
from eth2spec.phase0 import spec


def create_suite(operation_name: str, config_name: str, get_cases: Callable[[], Iterable[gen_typing.TestCase]]) \
        -> Callable[[str], gen_typing.TestSuiteOutput]:
    def suite_definition(configs_path: str) -> gen_typing.TestSuiteOutput:
        presets = loader.load_presets(configs_path, config_name)
        spec.apply_constants_preset(presets)

        return ("%s_%s" % (operation_name, config_name), operation_name, gen_suite.render_suite(
            title="%s operation" % operation_name,
            summary="Test suite for %s type operation processing" % operation_name,
            forks_timeline="testing",
            forks=["phase0"],
            config=config_name,
            runner="operations",
            handler=operation_name,
            test_cases=get_cases()))
    return suite_definition


if __name__ == "__main__":
    gen_runner.run_generator("operations", [
        create_suite('attestation',       'minimal', lambda: generate_from_tests(test_process_attestation)),
        create_suite('attestation',       'mainnet', lambda: generate_from_tests(test_process_attestation)),
        create_suite('attester_slashing', 'minimal', lambda: generate_from_tests(test_process_attester_slashing)),
        create_suite('attester_slashing', 'mainnet', lambda: generate_from_tests(test_process_attester_slashing)),
        create_suite('block_header',      'minimal', lambda: generate_from_tests(test_process_block_header)),
        create_suite('block_header',      'mainnet', lambda: generate_from_tests(test_process_block_header)),
        create_suite('deposit',          'minimal', lambda: generate_from_tests(test_process_deposit)),
        create_suite('deposit',          'mainnet', lambda: generate_from_tests(test_process_deposit)),
        create_suite('proposer_slashing', 'minimal', lambda: generate_from_tests(test_process_proposer_slashing)),
        create_suite('proposer_slashing', 'mainnet', lambda: generate_from_tests(test_process_proposer_slashing)),
        create_suite('transfer',          'minimal', lambda: generate_from_tests(test_process_transfer)),
        create_suite('transfer',          'mainnet', lambda: generate_from_tests(test_process_transfer)),
        create_suite('voluntary_exit',    'minimal', lambda: generate_from_tests(test_process_voluntary_exit)),
        create_suite('voluntary_exit',    'mainnet', lambda: generate_from_tests(test_process_voluntary_exit)),
    ])
