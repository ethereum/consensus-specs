from eth2spec.test.context import (
    spec_state_test,
    with_light_client,
    with_test_suite_name,
)


@with_test_suite_name("BeaconState")
@with_light_client
@spec_state_test
def test_current_sync_committee_merkle_proof(spec, state):
    yield "object", state
    current_sync_committee_branch = spec.compute_merkle_proof_for_state(
        state, spec.CURRENT_SYNC_COMMITTEE_INDEX)
    yield "proof", {
        "leaf": "0x" + state.current_sync_committee.hash_tree_root().hex(),
        "leaf_index": spec.CURRENT_SYNC_COMMITTEE_INDEX,
        "branch": ['0x' + root.hex() for root in current_sync_committee_branch]
    }
    assert spec.is_valid_merkle_branch(
        leaf=state.current_sync_committee.hash_tree_root(),
        branch=current_sync_committee_branch,
        depth=spec.floorlog2(spec.CURRENT_SYNC_COMMITTEE_INDEX),
        index=spec.get_subtree_index(spec.CURRENT_SYNC_COMMITTEE_INDEX),
        root=state.hash_tree_root(),
    )


@with_test_suite_name("BeaconState")
@with_light_client
@spec_state_test
def test_next_sync_committee_merkle_proof(spec, state):
    yield "object", state
    next_sync_committee_branch = spec.compute_merkle_proof_for_state(
        state, spec.NEXT_SYNC_COMMITTEE_INDEX)
    yield "proof", {
        "leaf": "0x" + state.next_sync_committee.hash_tree_root().hex(),
        "leaf_index": spec.NEXT_SYNC_COMMITTEE_INDEX,
        "branch": ['0x' + root.hex() for root in next_sync_committee_branch]
    }
    assert spec.is_valid_merkle_branch(
        leaf=state.next_sync_committee.hash_tree_root(),
        branch=next_sync_committee_branch,
        depth=spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX),
        index=spec.get_subtree_index(spec.NEXT_SYNC_COMMITTEE_INDEX),
        root=state.hash_tree_root(),
    )


@with_test_suite_name("BeaconState")
@with_light_client
@spec_state_test
def test_finality_root_merkle_proof(spec, state):
    yield "object", state
    finality_branch = spec.compute_merkle_proof_for_state(
        state, spec.FINALIZED_ROOT_INDEX)
    yield "proof", {
        "leaf": "0x" + state.finalized_checkpoint.root.hex(),
        "leaf_index": spec.FINALIZED_ROOT_INDEX,
        "branch": ['0x' + root.hex() for root in finality_branch]
    }

    assert spec.is_valid_merkle_branch(
        leaf=state.finalized_checkpoint.root,
        branch=finality_branch,
        depth=spec.floorlog2(spec.FINALIZED_ROOT_INDEX),
        index=spec.get_subtree_index(spec.FINALIZED_ROOT_INDEX),
        root=state.hash_tree_root(),
    )
