from eth_consensus_specs.test.gloas.block_processing.test_process_payload_attestation import (
    prepare_signed_payload_attestation,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    setup_one_block_store,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


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


def ptc_size_balances(spec):
    """
    Return a balances list sized to PTC_SIZE so each PTC seat can be pinned to a unique validator.
    """
    return [spec.MAX_EFFECTIVE_BALANCE] * spec.PTC_SIZE


def setup_verified_parent_with_distinct_ptc(spec, state):
    """
    Build a Gloas store with one block at state.slot+1 whose envelope has been delivered,
    and pin each PTC seat for that slot to a distinct validator so each cast vote later
    lands on exactly one position.
    """
    block_slot = state.slot + 1
    window_idx = spec.SLOTS_PER_EPOCH + block_slot % spec.SLOTS_PER_EPOCH
    for i in range(spec.PTC_SIZE):
        state.ptc_window[window_idx][i] = spec.ValidatorIndex(i)

    store, block_root, block_state, signed_block, test_steps = yield from setup_one_block_store(
        spec, state
    )
    envelope = build_signed_execution_payload_envelope(spec, block_state, block_root, signed_block)
    yield from add_execution_payload(spec, store, envelope, test_steps)
    return store, block_root, block_state, test_steps


def vote_via_child_block(
    spec,
    store,
    parent_root,
    parent_state,
    positions,
    test_steps,
    payload_present=True,
    blob_data_available=True,
):
    """
    Deliver PTC votes for parent_root through a child block at parent_state.slot + 1
    that carries a PayloadAttestation aggregate.
    """
    aggregate = prepare_signed_payload_attestation(
        spec,
        parent_state,
        slot=parent_state.slot,
        beacon_block_root=parent_root,
        payload_present=payload_present,
        blob_data_available=blob_data_available,
        attesting_indices=[spec.ValidatorIndex(p) for p in positions],
    )

    child_state = parent_state.copy()
    child_block = build_empty_block_for_next_slot(spec, child_state)
    child_block.body.payload_attestations.append(aggregate)
    signed_child = state_transition_and_sign_block(spec, child_state, child_block)
    yield from tick_and_add_block(spec, store, signed_child, test_steps)
