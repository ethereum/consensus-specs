from copy import deepcopy

from eth2spec.test.context import (
    spec_state_test_with_matching_config,
    with_config_overrides,
    with_light_client,
    with_presets,
)
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.light_client import (
    create_update,
    sample_blob_schedule,
)
from eth2spec.test.helpers.state import (
    next_slots,
)


def setup_test(spec, state):
    trusted_block = spec.SignedBeaconBlock()
    trusted_block.message.state_root = state.hash_tree_root()
    trusted_block_root = trusted_block.message.hash_tree_root()
    bootstrap = spec.create_light_client_bootstrap(state, trusted_block)
    store = spec.initialize_light_client_store(trusted_block_root, bootstrap)
    store.next_sync_committee = state.next_sync_committee

    return (trusted_block, store)


@with_light_client
@spec_state_test_with_matching_config
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(),
    },
)
def test_process_light_client_update_not_timeout(spec, state):
    genesis_block, store = setup_test(spec, state)

    # Block at slot 1 doesn't increase sync committee period, so it won't force update store.finalized_header
    attested_block = state_transition_with_full_block(spec, state, False, False)
    signature_slot = state.slot + 1

    # Ensure that finality checkpoint is genesis
    assert state.finalized_checkpoint.epoch == 0

    update = create_update(
        spec,
        attested_state=state,
        attested_block=attested_block,
        finalized_block=genesis_block,
        with_next=False,
        with_finality=False,
        participation_rate=1.0,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0


@with_light_client
@spec_state_test_with_matching_config
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(),
    },
)
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_at_period_boundary(spec, state):
    genesis_block, store = setup_test(spec, state)

    # Forward to slot before next sync committee period so that next block is final one in period
    next_slots(spec, state, spec.UPDATE_TIMEOUT - 2)
    store_period = spec.compute_sync_committee_period_at_slot(store.optimistic_header.beacon.slot)
    update_period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert store_period == update_period

    attested_block = state_transition_with_full_block(spec, state, False, False)
    signature_slot = state.slot + 1

    update = create_update(
        spec,
        attested_state=state,
        attested_block=attested_block,
        finalized_block=genesis_block,
        with_next=False,
        with_finality=False,
        participation_rate=1.0,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0


@with_light_client
@spec_state_test_with_matching_config
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(),
    },
)
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_timeout(spec, state):
    genesis_block, store = setup_test(spec, state)

    # Forward to next sync committee period
    next_slots(spec, state, spec.UPDATE_TIMEOUT)
    store_period = spec.compute_sync_committee_period_at_slot(store.optimistic_header.beacon.slot)
    update_period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert store_period + 1 == update_period

    attested_block = state_transition_with_full_block(spec, state, False, False)
    signature_slot = state.slot + 1

    update = create_update(
        spec,
        attested_state=state,
        attested_block=attested_block,
        finalized_block=genesis_block,
        with_next=True,
        with_finality=False,
        participation_rate=1.0,
    )

    pre_store = deepcopy(store)

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == pre_store.finalized_header
    assert store.best_valid_update == update
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0


@with_light_client
@spec_state_test_with_matching_config
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(),
    },
)
@with_presets([MINIMAL], reason="too slow")
def test_process_light_client_update_finality_updated(spec, state):
    _, store = setup_test(spec, state)

    # Change finality
    blocks = []
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)
    for epoch in range(3):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, True)
        blocks += new_blocks
    # Ensure that finality checkpoint has changed
    assert state.finalized_checkpoint.epoch == 3
    # Ensure that it's same period
    store_period = spec.compute_sync_committee_period_at_slot(store.optimistic_header.beacon.slot)
    update_period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert store_period == update_period

    attested_block = blocks[-1]
    signature_slot = state.slot + 1

    # Updated finality
    finalized_block = blocks[spec.SLOTS_PER_EPOCH - 1]
    assert finalized_block.message.slot == spec.compute_start_slot_at_epoch(
        state.finalized_checkpoint.epoch
    )
    assert finalized_block.message.hash_tree_root() == state.finalized_checkpoint.root

    update = create_update(
        spec,
        attested_state=state,
        attested_block=attested_block,
        finalized_block=finalized_block,
        with_next=False,
        with_finality=True,
        participation_rate=1.0,
    )

    spec.process_light_client_update(store, update, signature_slot, state.genesis_validators_root)

    assert store.finalized_header == update.finalized_header
    assert store.best_valid_update is None
    assert store.optimistic_header == update.attested_header
    assert store.current_max_active_participants > 0
