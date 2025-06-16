from eth2spec.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth2spec.test.helpers.constants import (
    ELECTRA,
    FULU,
)
from eth2spec.test.helpers.fork_transition import do_fork_generate
from eth2spec.test.helpers.fulu.fork import (
    FULU_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth2spec.test.helpers.state import (
    cause_effective_balance_decrease_below_threshold,
    simulate_lookahead,
    simulate_lookahead_with_thresholds,
)
from eth2spec.test.helpers.withdrawals import set_compounding_withdrawal_credential
from eth2spec.test.utils import with_meta_tags


@with_phases(phases=[ELECTRA], other_phases=[FULU])
@spec_test
@with_state
@with_meta_tags(FULU_FORK_TEST_META_TAGS)
def test_lookahead_consistency_at_fork(spec, phases, state):
    """
    Test that lookahead is consistent before/after the Fulu fork.
    """

    # Calculate the current and next epoch lookahead by simulating the state progression
    # with empty slots and calling `get_beacon_proposer_index` (how it was done pre-Fulu)
    pre_fork_proposers = simulate_lookahead(spec, state)

    # Upgrade to Fulu
    spec = phases[FULU]
    state = yield from run_fork_test(spec, state)

    # Check if the pre-fork simulation matches the post-fork `state.proposer_lookahead`
    assert pre_fork_proposers == state.proposer_lookahead


@with_phases(phases=[ELECTRA], other_phases=[FULU])
@spec_test
@with_state
@with_meta_tags(FULU_FORK_TEST_META_TAGS)
def test_lookahead_consistency_with_effective_balance_change_at_fork(spec, phases, state):
    # Move to the last slot of the current epoch
    spec.process_slots(
        state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    )
    assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

    # Calculate the lookahead of next epoch, including the thresholds of effective balance that
    # make a validator be a proposer at each slot.
    next_epoch_lookahead_threshold = simulate_lookahead_with_thresholds(spec, state)[
        spec.SLOTS_PER_EPOCH :
    ]
    next_epoch_lookahead = simulate_lookahead(spec, state)[spec.SLOTS_PER_EPOCH :]
    assert next_epoch_lookahead_threshold[0][0] == next_epoch_lookahead[0], (
        "The first index in the lookahead should match the first index in the threshold lookahead."
    )

    # Change the validator balance enough to trigger a change in the effective balance that goes below the threshold.
    validator_change_index = next_epoch_lookahead_threshold[0][0]
    validator_change_threshold = next_epoch_lookahead_threshold[0][1]
    set_compounding_withdrawal_credential(spec, state, validator_change_index)
    cause_effective_balance_decrease_below_threshold(
        spec, state, validator_change_index, validator_change_threshold
    )

    state, _ = yield from do_fork_generate(
        state, spec, phases[FULU], spec.get_current_epoch(state) + 1
    )

    # Calculate the actual lookahead
    actual_lookahead = simulate_lookahead(spec, state)[: spec.SLOTS_PER_EPOCH]

    # Because the Electra epoch processing is always run right before the Fulu upgrade,
    # the proposers lookahead will change depending on the effective balance change.
    assert next_epoch_lookahead != actual_lookahead
