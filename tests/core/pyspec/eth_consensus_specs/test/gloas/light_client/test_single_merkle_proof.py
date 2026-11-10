from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases_from_except,
    with_test_suite_name,
)
from eth_consensus_specs.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth_consensus_specs.test.helpers.constants import GLOAS, PQ


@with_test_suite_name("BeaconBlockBody")
@with_all_phases_from_except(GLOAS, [PQ])
@spec_state_test
def test_execution_block_hash_merkle_proof(spec, state):
    block = state_transition_with_full_block(
        spec, state, fill_cur_epoch=True, fill_prev_epoch=False
    )

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
