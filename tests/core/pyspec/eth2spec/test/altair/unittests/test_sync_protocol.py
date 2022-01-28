from copy import deepcopy

from eth2spec.test.context import (
    spec_state_test,
    with_presets,
    with_altair_and_later,
)
from eth2spec.test.helpers.attestations import next_epoch_with_attestations
from eth2spec.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.state import (
    next_slots,
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.helpers.merkle import build_proof


def _initialize_light_client_store(spec, state):
    return spec.LightClientStore(
        finalized_header=spec.BeaconBlockHeader(),
        current_sync_committee=state.current_sync_committee,
        next_sync_committee=state.next_sync_committee,
        best_valid_update=None,
        optimistic_header=spec.BeaconBlockHeader(),
        previous_max_active_participants=0,
        current_max_active_participants=0,
    )


@with_altair_and_later
@spec_state_test
def test_process_light_client_update_not_timeout(spec, state):
    store = _initialize_light_client_store(spec, state)

    # Block at slot 1 doesn't increase sync committee period, so it won't force update store.finalized_header
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_header = spec.BeaconBlockHeader(
        slot=signed_block.message.slot,
        proposer_index=signed_block.message.proposer_index,
        parent_root=signed_block.message.parent_root,
        state_root=signed_block.message.state_root,
        body_root=signed_block.message.body.hash_tree_root(),
    )
    # Sync committee signing the header
    all_pubkeys = [v.pubkey for v in state.validators]
    committee = [all_pubkeys.index(pubkey) for pubkey in state.current_sync_committee.pubkeys]
    sync_committee_bits = [True] * len(committee)
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        block_header.slot,
        committee,
    )
    sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )
    next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]

    # Ensure that finality checkpoint is genesis
    assert state.finalized_checkpoint.epoch == 0
    # Finality is unchanged
    finality_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        attested_header=block_header,
        next_sync_committee=state.next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finality_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        fork_version=state.fork.current_version,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)

    assert store.current_max_active_participants > 0
    assert store.optimistic_header == update.attested_header
    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_timeout(spec, state):
    store = _initialize_light_client_store(spec, state)

    # Forward to next sync committee period
    next_slots(spec, state, spec.UPDATE_TIMEOUT)
    snapshot_period = spec.compute_epoch_at_slot(store.optimistic_header.slot) // spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    update_period = spec.compute_epoch_at_slot(state.slot) // spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert snapshot_period + 1 == update_period

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_header = spec.BeaconBlockHeader(
        slot=signed_block.message.slot,
        proposer_index=signed_block.message.proposer_index,
        parent_root=signed_block.message.parent_root,
        state_root=signed_block.message.state_root,
        body_root=signed_block.message.body.hash_tree_root(),
    )

    # Sync committee signing the finalized_block_header
    all_pubkeys = [v.pubkey for v in state.validators]
    committee = [all_pubkeys.index(pubkey) for pubkey in state.current_sync_committee.pubkeys]
    sync_committee_bits = [True] * len(committee)
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        block_header.slot,
        committee,
        block_root=spec.Root(block_header.hash_tree_root()),
    )
    sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )

    # Sync committee is updated
    next_sync_committee_branch = build_proof(state.get_backing(), spec.NEXT_SYNC_COMMITTEE_INDEX)
    # Finality is unchanged
    finality_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        attested_header=block_header,
        next_sync_committee=state.next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finality_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        fork_version=state.fork.current_version,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)

    assert store.current_max_active_participants > 0
    assert store.optimistic_header == update.attested_header
    assert store.best_valid_update == update
    assert store.finalized_header == pre_store.finalized_header


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_finality_updated(spec, state):
    store = _initialize_light_client_store(spec, state)

    # Change finality
    blocks = []
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)
    for epoch in range(3):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, True)
        blocks += new_blocks
    # Ensure that finality checkpoint has changed
    assert state.finalized_checkpoint.epoch == 3
    # Ensure that it's same period
    snapshot_period = spec.compute_epoch_at_slot(store.optimistic_header.slot) // spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    update_period = spec.compute_epoch_at_slot(state.slot) // spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert snapshot_period == update_period

    # Updated sync_committee and finality
    next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]
    finalized_block_header = blocks[spec.SLOTS_PER_EPOCH - 1].message
    assert finalized_block_header.slot == spec.compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)
    assert finalized_block_header.hash_tree_root() == state.finalized_checkpoint.root
    finality_branch = build_proof(state.get_backing(), spec.FINALIZED_ROOT_INDEX)

    # Build block header
    block = build_empty_block(spec, state)
    block_header = spec.BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=state.hash_tree_root(),
        body_root=block.body.hash_tree_root(),
    )

    # Sync committee signing the finalized_block_header
    all_pubkeys = [v.pubkey for v in state.validators]
    committee = [all_pubkeys.index(pubkey) for pubkey in state.current_sync_committee.pubkeys]
    sync_committee_bits = [True] * len(committee)
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        block_header.slot,
        committee,
        block_root=spec.Root(block_header.hash_tree_root()),
    )
    sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )

    update = spec.LightClientUpdate(
        attested_header=block_header,
        next_sync_committee=state.next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_block_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        fork_version=state.fork.current_version,
    )

    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)

    assert store.current_max_active_participants > 0
    assert store.optimistic_header == update.attested_header
    assert store.finalized_header == update.finalized_header
    assert store.best_valid_update is None
