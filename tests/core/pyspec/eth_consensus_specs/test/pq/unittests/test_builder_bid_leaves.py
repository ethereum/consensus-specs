from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import builder_privkeys


def sign_bid_at_leaf(spec, state, leaf_index):
    bid = spec.ExecutionPayloadBid(slot=state.slot, builder_index=0)
    signature = spec.get_execution_payload_bid_signature(
        state, bid, builder_privkeys[0], leaf_index
    )
    return spec.SignedExecutionPayloadBid(message=bid, signature=signature)


@with_phases([PQ])
@spec_state_test
def test_bid_signed_at_first_bid_leaf(spec, state):
    leaf_index = spec.XMSS_RESERVED_LEAVES + spec.XMSS_ATTESTATION_LEAVES
    signed_bid = sign_bid_at_leaf(spec, state, leaf_index)
    assert spec.verify_execution_payload_bid_signature(state, signed_bid)


@with_phases([PQ])
@spec_state_test
def test_bid_signed_at_last_bid_leaf(spec, state):
    leaf_index = (
        spec.XMSS_RESERVED_LEAVES + spec.XMSS_ATTESTATION_LEAVES + spec.XMSS_BUILDER_BID_LEAVES - 1
    )
    signed_bid = sign_bid_at_leaf(spec, state, leaf_index)
    assert spec.verify_execution_payload_bid_signature(state, signed_bid)


@with_phases([PQ])
@spec_state_test
def test_bid_signed_at_attestation_leaf(spec, state):
    leaf_index = spec.compute_xmss_attestation_leaf_index(spec.get_current_epoch(state))
    signed_bid = sign_bid_at_leaf(spec, state, leaf_index)
    assert not spec.verify_execution_payload_bid_signature(state, signed_bid)


@with_phases([PQ])
@spec_state_test
def test_bid_signed_at_slot_leaf(spec, state):
    leaf_index = spec.compute_xmss_leaf_index(state.slot, spec.LEAF_OFFSET_BEACON_PROPOSER)
    signed_bid = sign_bid_at_leaf(spec, state, leaf_index)
    assert not spec.verify_execution_payload_bid_signature(state, signed_bid)
