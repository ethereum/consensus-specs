from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
    with_test_suite_name,
)
from eth_consensus_specs.test.helpers.attestations import (
    state_transition_with_full_block,
)


@with_test_suite_name("BeaconBlockBody")
@with_gloas_and_later
@spec_state_test
def test_execution_block_hash_merkle_proof(spec, state):
    block = state_transition_with_full_block(spec, state, True, False)

    yield "object", block.message.body
    gindex = spec.EXECUTION_BLOCK_HASH_GINDEX_GLOAS
    branch = spec.compute_merkle_proof(block.message.body, gindex)
    yield (
        "proof",
        {
            "leaf": "0x"
            + block.message.body.signed_execution_payload_bid.message.parent_block_hash.hex(),
            "leaf_index": gindex,
            "branch": ["0x" + root.hex() for root in branch],
        },
    )
    assert spec.is_valid_merkle_branch(
        leaf=block.message.body.signed_execution_payload_bid.message.parent_block_hash,
        branch=branch,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=block.message.body.hash_tree_root(),
    )
