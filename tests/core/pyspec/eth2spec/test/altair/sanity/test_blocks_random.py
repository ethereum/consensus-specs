from tests.core.pyspec.eth2spec.test.helpers.constants import ALTAIR
from tests.core.pyspec.eth2spec.test.context import (
    misc_balances_in_default_range_with_many_validators,
    with_phases,
    zero_activation_threshold,
)
from eth2spec.test.helpers.multi_operations import (
    get_random_sync_aggregate,
)
from eth2spec.test.helpers.inactivity_scores import (
    randomize_inactivity_scores,
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
    random_block,
    randomize_state,
)

SYNC_AGGREGATE_PARTICIPATION_BUCKETS = 4


def _randomize_altair_state(spec, state):
    randomize_state(spec, state, exit_fraction=0.1, slash_fraction=0.1)
    randomize_inactivity_scores(spec, state)


def _randomize_altair_block(spec, state, signed_blocks):
    block = random_block(spec, state, signed_blocks)
    fraction_missed = len(signed_blocks) / SYNC_AGGREGATE_PARTICIPATION_BUCKETS
    fraction_participated = 1.0 - fraction_missed
    block.body.sync_aggregate = get_random_sync_aggregate(spec, state, fraction_participated=fraction_participated)
    return block


def pytest_generate_tests(metafunc):
    """
    Pytest hook to generate test cases from dynamically computed data
    """
    generate_randomized_tests(
        metafunc,
        state_randomizer=_randomize_altair_state,
        block_randomizer=_randomize_altair_block,
    )


@pytest_generate_tests_adapter
@with_phases([ALTAIR])
@with_custom_state(
    balances_fn=misc_balances_in_default_range_with_many_validators,
    threshold_fn=zero_activation_threshold
)
@spec_test
@single_phase
@always_bls
def test_harness_for_randomized_blocks(spec, state, test_description):
    yield from run_generated_randomized_test(spec, state, test_description)
