from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_eip8321_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.eip8321.randao import (
    get_commitment,
    get_signed_registration,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


@with_eip8321_and_later
@spec_state_test
def test_randao_commitment_registration_lifecycle(spec, state):
    """
    Register the whole validator set, then walk to the activation epoch and check
    that proposers switch from the legacy BLS reveal to their hash chains.
    """
    registrations = [
        get_signed_registration(spec, state, validator_index=index)
        for index in range(len(state.validators))
    ]

    yield "pre", state

    # Spread across blocks in one epoch to respect the per-block cap
    inclusion_epoch = spec.get_current_epoch(state)
    capacity = int(spec.MAX_RANDAO_COMMITMENT_REGISTRATIONS)
    blocks = []
    for start in range(0, len(registrations), capacity):
        block = build_empty_block_for_next_slot(spec, state)
        block.body.randao_commitment_registrations = spec.RandaoCommitmentRegistrations(
            data=registrations[start : start + capacity]
        )
        blocks.append(state_transition_and_sign_block(spec, state, block))
    assert spec.get_current_epoch(state) == inclusion_epoch

    # The registrations are queued, and every validator is still on the legacy path
    assert len(state.pending_randao_commitments) == len(registrations)
    assert all(commitment == spec.Bytes32() for commitment in state.randao_commitments)

    # Proposals stay on the legacy path for the epochs preceding activation
    for _ in range(spec.COMMITMENT_REGISTRATION_DELAY - 1):
        block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
        assert block.body.hash_chain_reveal == spec.Bytes32()
        assert block.body.randao_reveal != spec.G2_POINT_AT_INFINITY
        blocks.append(state_transition_and_sign_block(spec, state, block))
        assert all(commitment == spec.Bytes32() for commitment in state.randao_commitments)

    # Crossing into the activation epoch applies the whole queue
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    assert block.body.hash_chain_reveal != spec.Bytes32()
    assert block.body.randao_reveal == spec.G2_POINT_AT_INFINITY
    proposer_index = block.proposer_index
    blocks.append(state_transition_and_sign_block(spec, state, block))

    assert len(state.pending_randao_commitments) == 0
    for index in range(len(state.validators)):
        expected = get_commitment(spec, index)
        if index == proposer_index:
            # The proposer has walked one link back already
            assert state.randao_commitments[index] != expected
            assert (
                spec.blake3(spec.HASH_CHAIN_RANDAO_DST + state.randao_commitments[index])
                == expected
            )
        else:
            assert state.randao_commitments[index] == expected

    yield "blocks", blocks
    yield "post", state


def registration_cap_balances(spec):
    """
    One validator more than registrations fit in a block.
    """
    return [spec.MAX_EFFECTIVE_BALANCE] * (int(spec.MAX_RANDAO_COMMITMENT_REGISTRATIONS) + 1)


def build_block_with_registrations(spec, state, validator_indices):
    block = build_empty_block_for_next_slot(spec, state)
    block.body.randao_commitment_registrations = spec.RandaoCommitmentRegistrations(
        data=[
            get_signed_registration(spec, state, validator_index=index)
            for index in validator_indices
        ]
    )
    return block


@with_eip8321_and_later
@with_custom_state(balances_fn=registration_cap_balances, threshold_fn=default_activation_threshold)
@spec_test
@single_phase
def test_max_randao_commitment_registrations(spec, state):
    count = int(spec.MAX_RANDAO_COMMITMENT_REGISTRATIONS)
    block = build_block_with_registrations(spec, state, range(count))

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield "blocks", [signed_block]
    yield "post", state

    assert len(state.pending_randao_commitments) == count


@with_eip8321_and_later
@with_custom_state(balances_fn=registration_cap_balances, threshold_fn=default_activation_threshold)
@spec_test
@single_phase
def test_invalid_too_many_randao_commitment_registrations(spec, state):
    count = int(spec.MAX_RANDAO_COMMITMENT_REGISTRATIONS) + 1
    block = build_block_with_registrations(spec, state, range(count))

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)
    yield "blocks", [signed_block]
    yield "post", None


@with_eip8321_and_later
@spec_state_test
def test_invalid_duplicate_randao_commitment_registration_in_block(spec, state):
    # The second copy finds the first already queued
    block = build_block_with_registrations(spec, state, [0, 0])

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)
    yield "blocks", [signed_block]
    yield "post", None
