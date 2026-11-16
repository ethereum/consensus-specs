from eth_consensus_specs.test.context import (
    spec_state_test,
    with_config_overrides,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)


@with_gloas_and_later
@spec_state_test
def test_parent_payload_status__gloas_parent(spec, state):
    """
    A block which does not build on the payload of its Gloas parent has an
    empty parent, and the parent's payload is not verified until its envelope
    is imported.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    anchor_root = anchor_block.hash_tree_root()
    assert anchor_root not in store.payloads

    block = build_empty_block_for_next_slot(spec, state)
    parent_bid = anchor_block.body.signed_execution_payload_bid.message
    assert block.body.signed_execution_payload_bid.message.parent_payload_root != (
        parent_bid.payload_root
    )

    assert not spec.is_payload_verified(store, anchor_root)
    assert spec.get_parent_payload_status(store, block) == spec.PAYLOAD_STATUS_EMPTY


@with_gloas_and_later
@spec_state_test
@with_config_overrides({"GLOAS_FORK_EPOCH": 1})
def test_parent_payload_status__pre_gloas_parent(spec, state):
    """
    A block with a parent from before the Gloas fork has a full parent, as a
    pre-Gloas block contains its payload, and that payload is verified with
    the block. The same block as in the test above is used, with a fork epoch
    which makes its parent a pre-Gloas block.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    anchor_root = anchor_block.hash_tree_root()
    assert anchor_root not in store.payloads
    assert spec.compute_epoch_at_slot(anchor_block.slot) < spec.config.GLOAS_FORK_EPOCH

    block = build_empty_block_for_next_slot(spec, state)

    assert spec.is_payload_verified(store, anchor_root)
    assert spec.get_parent_payload_status(store, block) == spec.PAYLOAD_STATUS_FULL
    assert spec.is_parent_node_full(store, block)
