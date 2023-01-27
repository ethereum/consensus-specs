from eth2spec.test.context import (
    spec_state_test,
    with_capella_and_later,
    with_test_suite_name,
)
from eth2spec.test.helpers.attestations import (
    state_transition_with_full_block,
)


@with_test_suite_name("BeaconBlockBody")
@with_capella_and_later
@spec_state_test
def test_execution_merkle_proof(spec, state):
    block = state_transition_with_full_block(spec, state, True, False)

    yield "object", block.message.body
    execution_branch = spec.compute_merkle_proof_for_block_body(
        block.message.body, spec.EXECUTION_PAYLOAD_INDEX)
    yield "proof", {
        "leaf": "0x" + block.message.body.execution_payload.hash_tree_root().hex(),
        "leaf_index": spec.EXECUTION_PAYLOAD_INDEX,
        "branch": ['0x' + root.hex() for root in execution_branch]
    }
    assert spec.is_valid_merkle_branch(
        leaf=block.message.body.execution_payload.hash_tree_root(),
        branch=execution_branch,
        depth=spec.floorlog2(spec.EXECUTION_PAYLOAD_INDEX),
        index=spec.get_subtree_index(spec.EXECUTION_PAYLOAD_INDEX),
        root=block.message.body.hash_tree_root(),
    )
