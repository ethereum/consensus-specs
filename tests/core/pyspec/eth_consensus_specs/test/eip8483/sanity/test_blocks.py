from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.eip8483.block_processing.test_process_validator_pq_registration_request import (
    prepare_validator_pq_registration_request,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth_consensus_specs.test.helpers.constants import EIP8483
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
    set_parent_block_full,
)


@with_phases([EIP8483])
@spec_state_test
def test_voluntary_exit_after_parent_payload_pq_registration(spec, state):
    """
    Test that a voluntary exit removes a PQ registration made by the parent
    payload's requests in the same block, because the parent's execution
    requests are processed before the block's operations.
    """
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]

    # Move state forward SHARD_COMMITTEE_PERIOD epochs so the validator can exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH

    set_compounding_withdrawal_credential(spec, state, validator_index)
    requests = spec.ExecutionRequests(
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            prepare_validator_pq_registration_request(spec, state, validator_index, b"\x33" * 64)
        ),
    )
    set_parent_block_full(spec, state)
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    block.body.voluntary_exits = spec.VoluntaryExits(
        data=prepare_signed_exits(spec, state, [validator_index])
    )

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield "blocks", [signed_block]
    yield "post", state

    assert state.validators[validator_index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert len(state.validator_pq_registrations) == 0


@with_phases([EIP8483])
@spec_state_test
def test_bls_to_execution_change_and_parent_payload_pq_registration(spec, state):
    """
    Test that a validator with BLS credentials cannot switch to compounding and
    register PQ data with parent payload requests processed in the same block
    as its BLS to execution change, because the parent's execution requests are
    processed before the block's operations. The same requests in that block's
    own payload are processed in the next block, after the change, and succeed.
    """
    validator_index = 0
    validator = state.validators[validator_index]
    assert validator.withdrawal_credentials[:1] == spec.BLS_WITHDRAWAL_PREFIX

    address = b"\x22" * 20
    requests = spec.ExecutionRequests(
        consolidations=spec.ConsolidationRequests.of(
            spec.ConsolidationRequest(
                source_address=address,
                source_pubkey=validator.pubkey,
                target_pubkey=validator.pubkey,
            )
        ),
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            spec.ValidatorPQRegistrationRequest(
                source_address=address,
                validator_pubkey=validator.pubkey,
                pq_data=b"\x33" * 64,
            )
        ),
    )
    set_parent_block_full(spec, state)
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)

    block_1 = build_empty_block_for_next_slot(spec, state)
    block_1.body.parent_execution_requests = requests
    block_1.body.bls_to_execution_changes = spec.BLSToExecutionChanges.of(
        get_signed_address_change(spec, state, validator_index, to_execution_address=address)
    )
    # The payload of this block delivers the same requests to the next block
    bid = block_1.body.signed_execution_payload_bid.message
    bid.execution_requests_root = spec.hash_tree_root(requests)
    bid.block_hash = spec.Hash32(b"\x42" * 32)

    yield "pre", state
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    assert spec.has_eth1_withdrawal_credential(state.validators[validator_index])
    assert len(state.validator_pq_registrations) == 0

    block_2 = build_empty_block_for_next_slot(spec, state)
    block_2.body.signed_execution_payload_bid.message.parent_block_hash = (
        state.latest_execution_payload_bid.block_hash
    )
    block_2.body.parent_execution_requests = requests
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    assert spec.has_compounding_withdrawal_credential(state.validators[validator_index])
    assert [registration.validator_index for registration in state.validator_pq_registrations] == [
        validator_index
    ]
