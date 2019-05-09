from eth2spec.test.block_processing import (
    test_process_attestation,
    test_process_attester_slashing,
    test_process_block_header,
    test_process_deposit,
    test_process_proposer_slashing,
    test_process_transfer,
    test_process_voluntary_exit
)

from gen_base import gen_runner

from suite_creator import generate_from_tests, create_suite

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
