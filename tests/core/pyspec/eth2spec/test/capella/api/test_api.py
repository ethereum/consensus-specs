from eth2spec.test.helpers.hive import (
    StateID,
    EthV2DebugBeaconStates,
    EthV1BeaconStatesFinalityCheckpoints,
    EthV1BeaconStatesFork,
)
from eth2spec.test.context import (
    with_capella_and_later,
    spec_state_test,
    hive_state,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_slot,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.withdrawals import (
    prepare_expected_withdrawals,
)


def _perform_valid_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2,
        num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2)

    next_slot(spec, state)
    pre_next_withdrawal_index = state.next_withdrawal_index

    expected_withdrawals = spec.get_expected_withdrawals(state)

    pre_state = state.copy()

    # Block 1
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block)

    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(set(fully_withdrawable_indices).difference(set(withdrawn_indices)))
    partial_withdrawals_indices = list(set(partial_withdrawals_indices).difference(set(withdrawn_indices)))
    assert state.next_withdrawal_index == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD

    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(set(fully_withdrawable_indices).difference(set(withdrawn_indices)))
    partial_withdrawals_indices = list(set(partial_withdrawals_indices).difference(set(withdrawn_indices)))
    assert state.next_withdrawal_index == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD

    return pre_state, signed_block_1, pre_next_withdrawal_index


@with_capella_and_later
@spec_state_test
@hive_state
def test_debug_beacon_state_v2(spec, state):
    _, signed_block_1, pre_next_withdrawal_index = (_perform_valid_withdrawal(spec, state))

    # Block 2
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block)

    assert state.next_withdrawal_index == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2
    yield 'blocks', [signed_block_1, signed_block_2]
    yield 'post', state

    yield 'hive', [
        (
            EthV2DebugBeaconStates(id=StateID.Head()).
            from_state(state)
        ),
        (
            EthV2DebugBeaconStates(id=StateID.Slot(signed_block_2.message.slot)).
            from_state(state)
        ),
        (
            EthV1BeaconStatesFinalityCheckpoints(id=StateID.Head(), finalized=False).
            from_state(state)
        ),
        (
            EthV1BeaconStatesFork(id=StateID.Head(), finalized=False).
            from_state(state)
        )
    ]
