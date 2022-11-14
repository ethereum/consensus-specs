from copy import deepcopy

from eth2spec.test.context import (
    spec_state_test_with_matching_config,
    with_presets,
    with_altair_and_later,
)
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.light_client import (
    get_sync_aggregate,
    initialize_light_client_store,
    signed_block_to_header,
)
from eth2spec.test.helpers.state import (
    next_slots,
)


@with_altair_and_later
@spec_state_test_with_matching_config
def test_process_light_client_update_not_timeout(spec, state):
    store = initialize_light_client_store(spec, state)

    # Block at slot 1 doesn't increase sync committee period, so it won't force update store.finalized_header
    attested_block = state_transition_with_full_block(spec, state, False, False)
    attested_header = signed_block_to_header(spec, attested_block)

    # Sync committee signing the attested_header
    sync_aggregate, signature_slot = get_sync_aggregate(spec, state)
    next_sync_committee = spec.SyncCommittee()
    next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]

    # Ensure that finality checkpoint is genesis
    assert state.finalized_checkpoint.epoch == 0
    # Finality is unchanged
    finalized_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        attested_header=attested_header,
        next_sync_committee=next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        signature_slot=signature_slot,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0


@with_altair_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_at_period_boundary(spec, state):
    store = initialize_light_client_store(spec, state)

    # Forward to slot before next sync committee period so that next block is final one in period
    next_slots(spec, state, spec.UPDATE_TIMEOUT - 2)
    store_period = spec.compute_sync_committee_period_at_slot(store.optimistic_header.slot)
    update_period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert store_period == update_period

    attested_block = state_transition_with_full_block(spec, state, False, False)
    attested_header = signed_block_to_header(spec, attested_block)

    # Sync committee signing the attested_header
    sync_aggregate, signature_slot = get_sync_aggregate(spec, state)
    next_sync_committee = spec.SyncCommittee()
    next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]

    # Finality is unchanged
    finalized_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        attested_header=attested_header,
        next_sync_committee=next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        signature_slot=signature_slot,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0


@with_altair_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_timeout(spec, state):
    store = initialize_light_client_store(spec, state)

    # Forward to next sync committee period
    next_slots(spec, state, spec.UPDATE_TIMEOUT)
    store_period = spec.compute_sync_committee_period_at_slot(store.optimistic_header.slot)
    update_period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert store_period + 1 == update_period

    attested_block = state_transition_with_full_block(spec, state, False, False)
    attested_header = signed_block_to_header(spec, attested_block)

    # Sync committee signing the attested_header
    sync_aggregate, signature_slot = get_sync_aggregate(spec, state)

    # Sync committee is updated
    next_sync_committee = state.next_sync_committee
    next_sync_committee_branch = spec.compute_merkle_proof_for_state(state, spec.NEXT_SYNC_COMMITTEE_INDEX)
    # Finality is unchanged
    finalized_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        attested_header=attested_header,
        next_sync_committee=next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        signature_slot=signature_slot,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0


@with_altair_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_finality_updated(spec, state):
    store = initialize_light_client_store(spec, state)

    # Change finality
    blocks = []
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)
    for epoch in range(3):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, True)
        blocks += new_blocks
    # Ensure that finality checkpoint has changed
    assert state.finalized_checkpoint.epoch == 3
    # Ensure that it's same period
    store_period = spec.compute_sync_committee_period_at_slot(store.optimistic_header.slot)
    update_period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert store_period == update_period

    attested_block = blocks[-1]
    attested_header = signed_block_to_header(spec, attested_block)

    # Sync committee signing the attested_header
    sync_aggregate, signature_slot = get_sync_aggregate(spec, state)

    # Updated sync_committee and finality
    next_sync_committee = spec.SyncCommittee()
    next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]
    finalized_block = blocks[spec.SLOTS_PER_EPOCH - 1]
    finalized_header = signed_block_to_header(spec, finalized_block)
    assert finalized_header.slot == spec.compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)
    assert finalized_header.hash_tree_root() == state.finalized_checkpoint.root
    finality_branch = spec.compute_merkle_proof_for_state(state, spec.FINALIZED_ROOT_INDEX)

    update = spec.LightClientUpdate(
        attested_header=attested_header,
        next_sync_committee=next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        signature_slot=signature_slot,
    )

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == update.finalized_header
    assert store.best_valid_update is None
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0
