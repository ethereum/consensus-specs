from eth2spec.test.context import (
    spec_state_test,
    with_presets,
    with_phases,
)
from eth2spec.test.helpers.attestations import next_epoch_with_attestations
from eth2spec.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.constants import (
    ALTAIR,
    MINIMAL,
)
from eth2spec.test.helpers.state import (
    next_slots,
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.helpers.merkle import build_proof


@with_phases([ALTAIR])
@spec_state_test
def test_process_light_client_update_not_updated(spec, state):
    pre_snapshot = spec.LightClientSnapshot(
        header=spec.BeaconBlockHeader(),
        current_sync_committee=state.current_sync_committee,
        next_sync_committee=state.next_sync_committee,
    )
    store = spec.LightClientStore(
        snapshot=pre_snapshot,
        valid_updates=set(),
    )

    # Block at slot 1 doesn't increase sync committee period, so it won't update snapshot
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
        block.slot,
        committee,
    )
    next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]

    # Ensure that finality checkpoint is genesis
    assert state.finalized_checkpoint.epoch == 0
    # Finality is unchanged
    finality_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        header=block_header,
        next_sync_committee=state.next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finality_header=finality_header,
        finality_branch=finality_branch,
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
        fork_version=state.fork.current_version,
    )

    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)

    assert len(store.valid_updates) == 1
    assert store.valid_updates.pop() == update
    assert store.snapshot == pre_snapshot


@with_phases([ALTAIR])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_timeout(spec, state):
    pre_snapshot = spec.LightClientSnapshot(
        header=spec.BeaconBlockHeader(),
        current_sync_committee=state.current_sync_committee,
        next_sync_committee=state.next_sync_committee,
    )
    store = spec.LightClientStore(
        snapshot=pre_snapshot,
        valid_updates=set(),
    )

    # Forward to next sync committee period
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD))
    snapshot_period = spec.compute_epoch_at_slot(pre_snapshot.header.slot) // spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
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

    # Sync committee is updated
    next_sync_committee_branch = build_proof(state.get_backing(), spec.NEXT_SYNC_COMMITTEE_INDEX)
    # Finality is unchanged
    finality_header = spec.BeaconBlockHeader()
    finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    update = spec.LightClientUpdate(
        header=block_header,
        next_sync_committee=state.next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finality_header=finality_header,
        finality_branch=finality_branch,
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
        fork_version=state.fork.current_version,
    )

    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)

    # snapshot has been updated
    assert len(store.valid_updates) == 0
    assert store.snapshot.header == update.header


@with_phases([ALTAIR])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_finality_updated(spec, state):
    pre_snapshot = spec.LightClientSnapshot(
        header=spec.BeaconBlockHeader(),
        current_sync_committee=state.current_sync_committee,
        next_sync_committee=state.next_sync_committee,
    )
    store = spec.LightClientStore(
        snapshot=pre_snapshot,
        valid_updates=set(),
    )

    # Change finality
    blocks = []
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)
    for epoch in range(3):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, True)
        blocks += new_blocks
    # Ensure that finality checkpoint has changed
    assert state.finalized_checkpoint.epoch == 3
    # Ensure that it's same period
    snapshot_period = spec.compute_epoch_at_slot(pre_snapshot.header.slot) // spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
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

    update = spec.LightClientUpdate(
        header=finalized_block_header,
        next_sync_committee=state.next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finality_header=block_header,  # block_header is the signed header
        finality_branch=finality_branch,
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
        fork_version=state.fork.current_version,
    )

    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)

    # snapshot has been updated
    assert len(store.valid_updates) == 0
    assert store.snapshot.header == update.header
