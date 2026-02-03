from eth2spec.test.gloas.block_processing.test_process_payload_attestation import (
    prepare_signed_payload_attestation,
)


def get_random_payload_attestations(spec, state, rng):
    """Build random payload attestations for the parent block."""
    attested_slot = state.latest_block_header.slot
    # Don't generate payload attestation if we detect missed slots
    if attested_slot != state.slot or attested_slot == 0:
        return []

    # Compute the beacon_block_root from the parent block header
    parent_header = state.latest_block_header.copy()
    if parent_header.state_root == spec.Root():
        parent_header.state_root = spec.hash_tree_root(state)
    beacon_block_root = spec.hash_tree_root(parent_header)

    # Get ptc and select participants
    ptc = spec.get_ptc(state, attested_slot)
    if len(ptc) == 0:
        return []

    num_attesters = rng.randint(len(ptc) // 2, len(ptc))
    attesting_indices = rng.sample(list(ptc), num_attesters) if num_attesters > 0 else []
    if not attesting_indices:
        return []

    payload_attestation = prepare_signed_payload_attestation(
        spec,
        state,
        slot=attested_slot,
        beacon_block_root=beacon_block_root,
        payload_present=rng.choice([True, False]),
        attesting_indices=attesting_indices,
    )

    return [payload_attestation]
