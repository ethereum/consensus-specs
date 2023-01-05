from eth2spec.test.helpers.state import (
    transition_to,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
)
from math import floor


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


def create_update(spec,
                  attested_state,
                  attested_block,
                  finalized_block,
                  with_next,
                  with_finality,
                  participation_rate):
    num_participants = floor(spec.SYNC_COMMITTEE_SIZE * participation_rate)

    update = spec.LightClientUpdate()

    update.attested_header = spec.block_to_light_client_header(attested_block)

    if with_next:
        update.next_sync_committee = attested_state.next_sync_committee
        update.next_sync_committee_branch = spec.compute_merkle_proof_for_state(
            attested_state, spec.NEXT_SYNC_COMMITTEE_INDEX)

    if with_finality:
        update.finalized_header = spec.block_to_light_client_header(finalized_block)
        update.finality_branch = spec.compute_merkle_proof_for_state(
            attested_state, spec.FINALIZED_ROOT_INDEX)

    update.sync_aggregate, update.signature_slot = get_sync_aggregate(
        spec, attested_state, num_participants)

    return update
