from eth2spec.test.context import (
    spec_state_test,
    with_phases,
)
from eth2spec.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import ELECTRA, FULU
from eth2spec.test.helpers.state import (
    next_epoch,
    simulate_lookahead,
)
from eth2spec.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
)


def run_test_effective_balance_increase_changes_lookahead(spec, state, expect_lookahead_changed):
    # Advance few epochs to adjust the RANDAO
    next_epoch(spec, state)
    next_epoch(spec, state)
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


@with_phases(phases=[ELECTRA, FULU])
@spec_state_test
def test_effective_balance_increase_changes_lookahead(spec, state):
    if spec.fork == ELECTRA:
        # Pre-EIP-7917, effective balance changes due to attestation rewards
        # changes the next epoch's lookahead
        expect_lookahead_changed = True
    else:
        # Post-EIP-7917, effective balance changes due to attestation rewards
        # do not change the next epoch's lookahead
        expect_lookahead_changed = False

    yield from run_test_effective_balance_increase_changes_lookahead(
        spec, state, expect_lookahead_changed=expect_lookahead_changed
    )
