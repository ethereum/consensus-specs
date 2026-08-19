from eth_consensus_specs.test.context import (
    spec_state_test,
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
    assert len(registrations) <= spec.MAX_RANDAO_COMMITMENT_REGISTRATIONS

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.randao_commitment_registrations = registrations
    blocks = [state_transition_and_sign_block(spec, state, block)]

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
                spec.blake3_hash(spec.HASH_CHAIN_RANDAO_DST + state.randao_commitments[index])
                == expected
            )
        else:
            assert state.randao_commitments[index] == expected

    yield "blocks", blocks
    yield "post", state
