from eth2spec.test.helpers.state import (
    transition_to,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
)


def signed_block_to_header(spec, block):
    return spec.BeaconBlockHeader(
        slot=block.message.slot,
        proposer_index=block.message.proposer_index,
        parent_root=block.message.parent_root,
        state_root=block.message.state_root,
        body_root=block.message.body.hash_tree_root(),
    )


def initialize_light_client_store(spec, state):
    return spec.LightClientStore(
        finalized_header=spec.BeaconBlockHeader(),
        current_sync_committee=state.current_sync_committee,
        next_sync_committee=state.next_sync_committee,
        best_valid_update=None,
        optimistic_header=spec.BeaconBlockHeader(),
        previous_max_active_participants=0,
        current_max_active_participants=0,
    )


def get_sync_aggregate(spec, state, num_participants=None, signature_slot=None):
    # By default, the sync committee signs the previous slot
    if signature_slot is None:
        signature_slot = state.slot + 1

    # Ensure correct sync committee and fork version are selected
    signature_state = state.copy()
    transition_to(spec, signature_state, signature_slot)

    # Fetch sync committee
    committee_indices = compute_committee_indices(signature_state)
    committee_size = len(committee_indices)

    # By default, use full participation
    if num_participants is None:
        num_participants = committee_size
    assert committee_size >= num_participants >= 0

    # Compute sync aggregate
    sync_committee_bits = [True] * num_participants + [False] * (committee_size - num_participants)
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        signature_state,
        signature_slot,
        committee_indices[:num_participants],
    )
    sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )
    return sync_aggregate, signature_slot
