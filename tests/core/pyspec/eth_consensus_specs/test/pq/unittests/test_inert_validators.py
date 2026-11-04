from eth_consensus_specs.test.context import (
    spec_state_test,
    with_pq_and_later,
)
from eth_consensus_specs.test.helpers.state import next_epoch
from eth_consensus_specs.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
)


@with_pq_and_later
@spec_state_test
def test_inert_validator_has_no_duties(spec, state):
    inert_index = 0
    epoch = spec.get_current_epoch(state)
    pre_total_active_balance = spec.get_total_active_balance(state)
    state.validators[inert_index].inert = True

    assert spec.is_active_validator(state.validators[inert_index], epoch)
    assert inert_index not in spec.get_active_validator_indices(state, epoch)
    assert inert_index not in spec.get_beacon_proposer_indices(state, epoch)
    start_slot = spec.compute_start_slot_at_epoch(epoch)
    for offset in range(spec.SLOTS_PER_EPOCH):
        slot = start_slot + offset
        for index in range(spec.get_committee_count_per_slot(state, epoch)):
            assert inert_index not in spec.get_beacon_committee(state, slot, index)
        assert inert_index not in spec.compute_ptc(state, slot)
    assert spec.get_total_active_balance(state) == (
        pre_total_active_balance - state.validators[inert_index].effective_balance
    )


@with_pq_and_later
@spec_state_test
def test_inert_validator_has_no_rewards_or_penalties(spec, state):
    inert_index = 0
    other_index = 1
    state.validators[inert_index].inert = True
    pre_inert_balance = state.balances[inert_index]
    pre_other_balance = state.balances[other_index]

    yield "pre", state

    # No attestations are included, so active validators are penalized
    for _ in range(3):
        next_epoch(spec, state)

    yield "post", state

    assert state.balances[inert_index] == pre_inert_balance
    assert state.balances[other_index] < pre_other_balance


@with_pq_and_later
@spec_state_test
def test_inert_validator_exits_with_withdrawal_request(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    inert_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, inert_index, address=address)
    state.validators[inert_index].inert = True
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[inert_index].pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield "pre", state
    yield "withdrawal_request", withdrawal_request

    spec.process_withdrawal_request(state, withdrawal_request)

    yield "post", state

    assert state.validators[inert_index].exit_epoch < spec.FAR_FUTURE_EPOCH
