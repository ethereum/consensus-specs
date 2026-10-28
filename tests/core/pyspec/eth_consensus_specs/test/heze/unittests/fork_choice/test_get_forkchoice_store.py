from eth_consensus_specs.test.context import spec_state_test, with_heze_and_later
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import wrap_genesis_block


@with_heze_and_later
@spec_state_test
def test_get_forkchoice_store_anchor_payload_satisfied(spec, state):
    """
    Test that the anchor's payload, once known, counts as satisfying the inclusion
    list constraints and is preferred over the empty variant in the next slot.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    anchor_root = anchor_block.hash_tree_root()
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, anchor_root, signed_anchor
    )
    assert not spec.is_payload_inclusion_list_satisfied(store, anchor_root)

    store.payloads[anchor_root] = signed_envelope.message

    assert spec.is_payload_inclusion_list_satisfied(store, anchor_root)

    spec.on_tick(store, spec.compute_time_at_slot_ms(store.genesis_time_ms, anchor_block.slot + 1))
    assert spec.should_extend_payload(store, anchor_root)
    head = spec.get_head(store)
    assert head.root == anchor_root
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL
