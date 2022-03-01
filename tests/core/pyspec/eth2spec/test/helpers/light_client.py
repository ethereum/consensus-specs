from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
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


def get_sync_aggregate(spec, state, block_header, block_root=None, signature_slot=None):
    if signature_slot is None:
        signature_slot = block_header.slot

    all_pubkeys = [v.pubkey for v in state.validators]
    committee = [all_pubkeys.index(pubkey) for pubkey in state.current_sync_committee.pubkeys]
    sync_committee_bits = [True] * len(committee)
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        block_header.slot,
        committee,
        block_root=block_root,
    )
    return spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )
