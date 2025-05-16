from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_except,
    with_test_suite_name,
)
from eth2spec.test.helpers.constants import (
    CAPELLA,
    EIP7732,
)
from eth2spec.test.helpers.attestations import (
    state_transition_with_full_block,
)


@with_test_suite_name("BeaconBlockBody")
@with_all_phases_from_except(CAPELLA, [EIP7732])
@spec_state_test
def test_execution_merkle_proof(spec, state):
    block = state_transition_with_full_block(spec, state, True, False)

    yield "object", block.message.body
    gindex = spec.EXECUTION_PAYLOAD_GINDEX
    branch = spec.compute_merkle_proof(block.message.body, gindex)
    yield "proof", {
        "leaf": "0x" + block.message.body.execution_payload.hash_tree_root().hex(),
        "leaf_index": gindex,
        "branch": ["0x" + root.hex() for root in branch],
    }
    assert spec.is_valid_merkle_branch(
        leaf=block.message.body.execution_payload.hash_tree_root(),
        branch=branch,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=block.message.body.hash_tree_root(),
    )
