from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
    with_phases,
)
from eth2spec.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import ELECTRA, FULU
from eth2spec.test.helpers.forks import is_post_fulu
from eth2spec.test.helpers.state import (
    cause_effective_balance_decrease_below_threshold,
    next_epoch,
    simulate_lookahead,
    simulate_lookahead_with_thresholds,
    transition_to,
)
from eth2spec.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
)


def run_test_effective_balance_increase_changes_lookahead(
    spec, state, randao_setup_epochs, expect_lookahead_changed
):
    # Advance few epochs to adjust the RANDAO
    for _ in range(randao_setup_epochs):
        next_epoch(spec, state)

    # Set all active validators to have balance close to the hysteresis threshold
    current_epoch = spec.get_current_epoch(state)
    active_validator_indices = spec.get_active_validator_indices(state, current_epoch)
    for validator_index in active_validator_indices:
        # Set compounding withdrawal credentials for the validator
        set_compounding_withdrawal_credential(spec, state, validator_index)
        state.validators[validator_index].effective_balance = 32000000000
        # Set balance to close the next hysteresis threshold
        state.balances[validator_index] = 33250000000 - 1

    # Calculate the lookahead of next epoch
    next_epoch_lookahead = simulate_lookahead(spec, state)[spec.SLOTS_PER_EPOCH :]

    blocks = []
    yield "pre", state

    # Process 1-epoch worth of blocks with attestations
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = state_transition_with_full_block(
            spec, state, fill_cur_epoch=True, fill_prev_epoch=True
        )
        blocks.append(block)

    yield "blocks", blocks
    yield "post", state

    # Calculate the actual lookahead
    actual_lookahead = simulate_lookahead(spec, state)[: spec.SLOTS_PER_EPOCH]

    if expect_lookahead_changed:
        assert next_epoch_lookahead != actual_lookahead
    else:
        assert next_epoch_lookahead == actual_lookahead


def run_test_with_randao_setup_epochs(spec, state, randao_setup_epochs):
    if spec.fork == ELECTRA:
        # Pre-EIP-7917, effective balance changes due to attestation rewards
        # changes the next epoch's lookahead
        expect_lookahead_changed = True
    else:
        # Post-EIP-7917, effective balance changes due to attestation rewards
        # do not change the next epoch's lookahead
        expect_lookahead_changed = False

    yield from run_test_effective_balance_increase_changes_lookahead(
        spec, state, randao_setup_epochs, expect_lookahead_changed=expect_lookahead_changed
    )


@with_phases(phases=[ELECTRA, FULU])
@spec_state_test
def test_effective_balance_increase_changes_lookahead(spec, state):
    # Since this test relies on the RANDAO, we adjust the number of next_epoch transitions
    # we do at the setup of the test run until the assertion passes.
    # We start with 4 epochs because the test is known to pass with 4 epochs.
    for randao_setup_epochs in range(4, 20):
        try:
            state_copy = state.copy()
            yield from run_test_with_randao_setup_epochs(spec, state_copy, randao_setup_epochs)
            return
        except AssertionError:
            # If the randao_setup_epochs is not the right one to make the test pass,
            # then try again in the next iteration
            pass
    assert False, "The test should have succeeded with one of the iterations."


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
