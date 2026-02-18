from eth_consensus_specs.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth_consensus_specs.test.helpers.forks import is_post_fulu
from eth_consensus_specs.test.helpers.state import (
    cause_effective_balance_decrease_below_threshold,
    simulate_lookahead,
    simulate_lookahead_with_thresholds,
    transition_to,
)
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
)


@with_electra_and_later
@spec_state_test
def test_effective_decrease_balance_updates_lookahead(spec, state):
    """
    Test that effective balance updates change the proposer lookahead with EIP-7917.
    """
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

    pre_eb = state.validators[validator_change_index].effective_balance

    # Transition to the last slot of the epoch
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    transition_to(spec, state, slot)

    # Do the epoch transition that should change the validator balance.
    yield "pre", state
    yield "slots", 1
    spec.process_slots(state, state.slot + 1)
    yield "post", state

    post_eb = state.validators[validator_change_index].effective_balance

    assert pre_eb != post_eb, "Effective balance should have changed."
    assert post_eb < validator_change_threshold, "Effective balance should be below the threshold."

    # Calculate the actual lookahead
    actual_lookahead = simulate_lookahead(spec, state)[: spec.SLOTS_PER_EPOCH]

    if not is_post_fulu(spec):
        # Pre-EIP-7917, effective balance changes changes the next epoch's lookahead
        assert next_epoch_lookahead != actual_lookahead
    else:
        # Post-EIP-7917, effective balance changes do not change the next epoch's lookahead
        assert next_epoch_lookahead == actual_lookahead
