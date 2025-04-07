from eth2spec.test.context import (
    spec_state_test,
    with_light_client,
    with_test_suite_name,
)
from eth2spec.test.helpers.light_client import (
    latest_current_sync_committee_gindex,
    latest_finalized_root_gindex,
    latest_next_sync_committee_gindex,
)


@with_test_suite_name("BeaconState")
@with_light_client
@spec_state_test
def test_current_sync_committee_merkle_proof(spec, state):
    yield "object", state
    gindex = latest_current_sync_committee_gindex(spec)
    branch = spec.compute_merkle_proof(state, gindex)
    yield "proof", {
        "leaf": "0x" + state.current_sync_committee.hash_tree_root().hex(),
        "leaf_index": gindex,
        "branch": ["0x" + root.hex() for root in branch],
    }
    assert spec.is_valid_merkle_branch(
        leaf=state.current_sync_committee.hash_tree_root(),
        branch=branch,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=state.hash_tree_root(),
    )


@with_test_suite_name("BeaconState")
@with_light_client
@spec_state_test
def test_next_sync_committee_merkle_proof(spec, state):
    yield "object", state
    gindex = latest_next_sync_committee_gindex(spec)
    branch = spec.compute_merkle_proof(state, gindex)
    yield "proof", {
        "leaf": "0x" + state.next_sync_committee.hash_tree_root().hex(),
        "leaf_index": gindex,
        "branch": ["0x" + root.hex() for root in branch],
    }
    assert spec.is_valid_merkle_branch(
        leaf=state.next_sync_committee.hash_tree_root(),
        branch=branch,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=state.hash_tree_root(),
    )


@with_test_suite_name("BeaconState")
@with_light_client
@spec_state_test
def test_finality_root_merkle_proof(spec, state):
    yield "object", state
    gindex = latest_finalized_root_gindex(spec)
    branch = spec.compute_merkle_proof(state, gindex)
    yield "proof", {
        "leaf": "0x" + state.finalized_checkpoint.root.hex(),
        "leaf_index": gindex,
        "branch": ["0x" + root.hex() for root in branch],
    }

    assert spec.is_valid_merkle_branch(
        leaf=state.finalized_checkpoint.root,
        branch=branch,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=state.hash_tree_root(),
    )
