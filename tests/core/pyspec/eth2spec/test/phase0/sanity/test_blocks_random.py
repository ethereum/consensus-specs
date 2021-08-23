from eth2spec.test.helpers.constants import PHASE0
from eth2spec.test.context import (
    misc_balances_in_default_range_with_many_validators,
    with_phases,
    zero_activation_threshold,
)
from eth2spec.test.context import (
    always_bls,
    spec_test,
    with_custom_state,
    single_phase,
)
from eth2spec.test.utils.random import (
    generate_randomized_tests,
    pytest_generate_tests_adapter,
    run_generated_randomized_test,
)


def pytest_generate_tests(metafunc):
    """
    Pytest hook to generate test cases from dynamically computed data
    """
    generate_randomized_tests(metafunc)


@pytest_generate_tests_adapter
@with_phases([PHASE0])
@with_custom_state(
    balances_fn=misc_balances_in_default_range_with_many_validators,
    threshold_fn=zero_activation_threshold
)
@spec_test
@single_phase
@always_bls
def test_harness_for_randomized_blocks(spec, state, test_description):
    yield from run_generated_randomized_test(spec, state, test_description)
