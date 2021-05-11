from eth2spec.test.context import (
    spec_state_test,
    with_phases,
)
from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.test.helpers.merkle import build_proof


@with_phases([ALTAIR])
@spec_state_test
def test_next_sync_committee_tree(spec, state):
    state.next_sync_committee: object = spec.SyncCommittee(
        pubkeys=[state.validators[i]for i in range(spec.SYNC_COMMITTEE_SIZE)]
    )
    next_sync_committee_branch = build_proof(state.get_backing(), spec.NEXT_SYNC_COMMITTEE_INDEX)
    assert spec.is_valid_merkle_branch(
        leaf=state.next_sync_committee.hash_tree_root(),
        branch=next_sync_committee_branch,
        depth=spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX),
        index=spec.get_subtree_index(spec.NEXT_SYNC_COMMITTEE_INDEX),
        root=state.hash_tree_root(),
    )


@with_phases([ALTAIR])
@spec_state_test
def test_finality_root_tree(spec, state):
    finality_branch = build_proof(state.get_backing(), spec.FINALIZED_ROOT_INDEX)
    assert spec.is_valid_merkle_branch(
        leaf=state.finalized_checkpoint.root,
        branch=finality_branch,
        depth=spec.floorlog2(spec.FINALIZED_ROOT_INDEX),
        index=spec.get_subtree_index(spec.FINALIZED_ROOT_INDEX),
        root=state.hash_tree_root(),
    )
