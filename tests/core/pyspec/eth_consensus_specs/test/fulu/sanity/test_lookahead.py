from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth_consensus_specs.test.helpers.constants import ELECTRA, FULU
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    simulate_lookahead,
)
from eth_consensus_specs.test.helpers.withdrawals import (
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
