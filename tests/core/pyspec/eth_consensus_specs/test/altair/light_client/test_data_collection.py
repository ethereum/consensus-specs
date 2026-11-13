from eth_consensus_specs.test.context import (
    spec_state_test_with_matching_config,
    with_config_overrides,
    with_light_client,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    MINIMAL,
)
from eth_consensus_specs.test.helpers.genesis import create_signed_genesis_block
from eth_consensus_specs.test.helpers.light_client import (
    compute_start_slot_at_sync_committee_period,
    sample_blob_schedule,
)
from eth_consensus_specs.test.helpers.light_client_data_collection import (
    add_new_block,
    BlockID,
    finish_lc_data_collection_test,
    get_lc_bootstrap_block_id,
    get_lc_update_attested_block_id,
    get_light_client_bootstrap,
    get_light_client_finality_update,
    get_light_client_optimistic_update,
    get_light_client_update_for_period,
    select_new_head,
    setup_lc_data_collection_test,
)


@with_light_client
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(initial_epoch=1, interval=1),
    },
)
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_light_client_data_collection(spec, state):
    # Start test
    test = yield from setup_lc_data_collection_test(spec, state)

    # Genesis block is post Altair and is finalized, so can be used as bootstrap
    genesis_bid = BlockID(
        slot=state.slot, root=create_signed_genesis_block(spec, state).message.hash_tree_root()
    )
    assert (
        get_lc_bootstrap_block_id(get_light_client_bootstrap(test, genesis_bid.root).data)
        == genesis_bid
    )

    # No blocks have been imported, so no other light client data is available
    period = spec.compute_sync_committee_period_at_slot(state.slot)
    assert get_light_client_update_for_period(test, period).spec is None
    assert get_light_client_finality_update(test).spec is None
    assert get_light_client_optimistic_update(test).spec is None

    # Start branch A with a block that has an empty sync aggregate
    spec_a, state_a, bid_1 = yield from add_new_block(test, spec, state, slot=1)
    yield from select_new_head(test, spec_a, bid_1)
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert get_light_client_update_for_period(test, period).spec is None
    assert get_light_client_finality_update(test).spec is None
    assert get_light_client_optimistic_update(test).spec is None

    # Start branch B with a block that has 1 participant
    spec_b, state_b, bid_2 = yield from add_new_block(
        test, spec, state, slot=2, num_sync_participants=1
    )
    yield from select_new_head(test, spec_b, bid_2)
    period = spec_b.compute_sync_committee_period_at_slot(state_b.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == genesis_bid
    )
    assert (
        get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == genesis_bid
    )
    assert (
        get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data)
        == genesis_bid
    )

    # Build on branch A, once more with an empty sync aggregate
    spec_a, state_a, bid_3 = yield from add_new_block(test, spec_a, state_a, slot=3)
    yield from select_new_head(test, spec_a, bid_3)
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert get_light_client_update_for_period(test, period).spec is None
    assert get_light_client_finality_update(test).spec is None
    assert get_light_client_optimistic_update(test).spec is None

    # Build on branch B, this time with an empty sync aggregate
    spec_b, state_b, bid_4 = yield from add_new_block(test, spec_b, state_b, slot=4)
    yield from select_new_head(test, spec_b, bid_4)
    period = spec_b.compute_sync_committee_period_at_slot(state_b.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == genesis_bid
    )
    assert (
        get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == genesis_bid
    )
    assert (
        get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data)
        == genesis_bid
    )

    # Build on branch B, once more with 1 participant
    spec_b, state_b, bid_5 = yield from add_new_block(
        test, spec_b, state_b, slot=5, num_sync_participants=1
    )
    yield from select_new_head(test, spec_b, bid_5)
    period = spec_b.compute_sync_committee_period_at_slot(state_b.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == genesis_bid
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_4
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_4

    # Build on branch B, this time with 3 participants
    spec_b, state_b, bid_6 = yield from add_new_block(
        test, spec_b, state_b, slot=6, num_sync_participants=3
    )
    yield from select_new_head(test, spec_b, bid_6)
    period = spec_b.compute_sync_committee_period_at_slot(state_b.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_5
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_5
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_5

    # Build on branch A, with 2 participants
    spec_a, state_a, bid_7 = yield from add_new_block(
        test, spec_a, state_a, slot=7, num_sync_participants=2
    )
    yield from select_new_head(test, spec_a, bid_7)
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_3
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_3
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_3

    # Branch A: epoch 1, slot 5
    slot = spec_a.compute_start_slot_at_epoch(1) + 5
    spec_a, state_a, bid_1_5 = yield from add_new_block(
        test, spec_a, state_a, slot=slot, num_sync_participants=4
    )
    yield from select_new_head(test, spec_a, bid_1_5)
    assert get_light_client_bootstrap(test, bid_7.root).spec is None
    assert get_light_client_bootstrap(test, bid_1_5.root).spec is None
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_7
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_7
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_7

    # Branch B: epoch 2, slot 4
    slot = spec_b.compute_start_slot_at_epoch(2) + 4
    spec_b, state_b, bid_2_4 = yield from add_new_block(
        test, spec_b, state_b, slot=slot, num_sync_participants=5
    )
    yield from select_new_head(test, spec_b, bid_2_4)
    assert get_light_client_bootstrap(test, bid_7.root).spec is None
    assert get_light_client_bootstrap(test, bid_1_5.root).spec is None
    assert get_light_client_bootstrap(test, bid_2_4.root).spec is None
    period = spec_b.compute_sync_committee_period_at_slot(state_b.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_6
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_6
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_6

    # Branch A: epoch 3, slot 0
    slot = spec_a.compute_start_slot_at_epoch(3) + 0
    spec_a, state_a, bid_3_0 = yield from add_new_block(
        test, spec_a, state_a, slot=slot, num_sync_participants=6
    )
    yield from select_new_head(test, spec_a, bid_3_0)
    assert get_light_client_bootstrap(test, bid_7.root).spec is None
    assert get_light_client_bootstrap(test, bid_1_5.root).spec is None
    assert get_light_client_bootstrap(test, bid_2_4.root).spec is None
    assert get_light_client_bootstrap(test, bid_3_0.root).spec is None
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_1_5
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_1_5
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_1_5

    # Branch A: fill epoch
    for _i in range(1, spec_a.SLOTS_PER_EPOCH):
        spec_a, state_a, bid_a = yield from add_new_block(test, spec_a, state_a)
        yield from select_new_head(test, spec_a, bid_a)
        assert get_light_client_bootstrap(test, bid_7.root).spec is None
        assert get_light_client_bootstrap(test, bid_1_5.root).spec is None
        assert get_light_client_bootstrap(test, bid_2_4.root).spec is None
        assert get_light_client_bootstrap(test, bid_3_0.root).spec is None
        period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
        assert (
            get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
            == bid_1_5
        )
        assert (
            get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_1_5
        )
        assert (
            get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data)
            == bid_1_5
        )
    assert state_a.slot == spec_a.compute_start_slot_at_epoch(4) - 1
    bid_3_n = bid_a

    # Branch A: epoch 4, slot 0
    slot = spec_a.compute_start_slot_at_epoch(4) + 0
    spec_a, state_a, bid_4_0 = yield from add_new_block(
        test, spec_a, state_a, slot=slot, num_sync_participants=6
    )
    yield from select_new_head(test, spec_a, bid_4_0)
    assert get_light_client_bootstrap(test, bid_7.root).spec is None
    assert get_light_client_bootstrap(test, bid_1_5.root).spec is None
    assert get_light_client_bootstrap(test, bid_2_4.root).spec is None
    assert get_light_client_bootstrap(test, bid_3_0.root).spec is None
    assert get_light_client_bootstrap(test, bid_4_0.root).spec is None
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_1_5
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_3_n
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_3_n

    # Branch A: fill epoch
    for _i in range(1, spec_a.SLOTS_PER_EPOCH):
        spec_a, state_a, bid_a = yield from add_new_block(test, spec_a, state_a)
        yield from select_new_head(test, spec_a, bid_a)
        assert get_light_client_bootstrap(test, bid_7.root).spec is None
        assert get_light_client_bootstrap(test, bid_1_5.root).spec is None
        assert get_light_client_bootstrap(test, bid_2_4.root).spec is None
        assert get_light_client_bootstrap(test, bid_3_0.root).spec is None
        assert get_light_client_bootstrap(test, bid_4_0.root).spec is None
        period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
        assert (
            get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
            == bid_1_5
        )
        assert (
            get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_3_n
        )
        assert (
            get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data)
            == bid_3_n
        )
    assert state_a.slot == spec_a.compute_start_slot_at_epoch(5) - 1
    bid_4_n = bid_a

    # Branch A: epoch 6, slot 2
    slot = spec_a.compute_start_slot_at_epoch(6) + 2
    spec_a, state_a, bid_6_2 = yield from add_new_block(
        test, spec_a, state_a, slot=slot, num_sync_participants=6
    )
    yield from select_new_head(test, spec_a, bid_6_2)
    assert get_lc_bootstrap_block_id(get_light_client_bootstrap(test, bid_7.root).data) == bid_7
    assert get_lc_bootstrap_block_id(get_light_client_bootstrap(test, bid_1_5.root).data) == bid_1_5
    assert get_light_client_bootstrap(test, bid_2_4.root).spec is None
    assert get_lc_bootstrap_block_id(get_light_client_bootstrap(test, bid_3_0.root).data) == bid_3_0
    assert get_light_client_bootstrap(test, bid_4_0.root).spec is None
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_1_5
    )
    assert get_lc_update_attested_block_id(get_light_client_finality_update(test).data) == bid_4_n
    assert get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data) == bid_4_n

    # Branch A: fill remainder of sync committee period
    period_start_slot = compute_start_slot_at_sync_committee_period(spec_a, period + 1)
    while state_a.slot < period_start_slot - 1:
        spec_a, state_a, bid_a = yield from add_new_block(
            test, spec_a, state_a, num_sync_participants=6
        )
        yield from select_new_head(test, spec_a, bid_a)
        assert (
            get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
            == bid_1_5
        )
    bid_boundary = bid_a

    # Branch A: miss first slot of next sync committee period,
    # so that the boundary block of its first epoch is `bid_boundary`
    slot = period_start_slot + 1
    spec_a, state_a, bid_a = yield from add_new_block(
        test, spec_a, state_a, slot=slot, num_sync_participants=6
    )
    yield from select_new_head(test, spec_a, bid_a)
    period = spec_a.compute_sync_committee_period_at_slot(state_a.slot)
    assert get_light_client_update_for_period(test, period).spec is None
    bid_first = bid_a

    # Branch A: first update with attested block in sync committee period
    spec_a, state_a, bid_a = yield from add_new_block(
        test, spec_a, state_a, num_sync_participants=6
    )
    yield from select_new_head(test, spec_a, bid_a)
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == bid_first
    )

    # Branch A: updates without sync committee finality do not replace `bid_first`,
    # including those that finalize `bid_boundary` via the first epoch of `period`
    num_boundary_finality_updates = 0
    while True:
        assert spec_a.compute_sync_committee_period_at_slot(state_a.slot + 1) == period
        attested_state = state_a
        attested_bid = bid_a
        spec_a, state_a, bid_a = yield from add_new_block(
            test, spec_a, state_a, num_sync_participants=6
        )
        yield from select_new_head(test, spec_a, bid_a)
        finality_update = get_light_client_finality_update(test).data
        assert get_lc_update_attested_block_id(finality_update) == attested_bid
        finalized_header = finality_update.finalized_header.beacon
        if finalized_header.slot >= period_start_slot:
            break
        if finalized_header.hash_tree_root() == bid_boundary.root:
            assert (
                spec_a.compute_start_slot_at_epoch(attested_state.finalized_checkpoint.epoch)
                == period_start_slot
            )
            num_boundary_finality_updates += 1
        assert (
            get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
            == bid_first
        )
    assert num_boundary_finality_updates > 0

    # Branch A: first update with sync committee finality replaces `bid_first`
    assert (
        get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
        == attested_bid
    )

    # Finish test
    yield from finish_lc_data_collection_test(test)


@with_light_client
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(initial_epoch=1, interval=1),
    },
)
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_light_client_data_collection_empty_epochs_after_genesis(spec, state):
    # Start test
    test = yield from setup_lc_data_collection_test(spec, state)
    genesis_block = create_signed_genesis_block(spec, state)
    genesis_bid = BlockID(slot=state.slot, root=genesis_block.message.hash_tree_root())

    # Skip the start slot of epoch 2, so that the genesis block is its checkpoint
    finalized_epoch = spec.GENESIS_EPOCH + 2
    slot = spec.compute_start_slot_at_epoch(finalized_epoch) + 1
    spec, state, bid = yield from add_new_block(
        test, spec, state, slot=slot, num_sync_participants=1
    )
    yield from select_new_head(test, spec, bid)
    period = spec.compute_sync_committee_period_at_slot(state.slot)

    # Finalize epoch 2
    while state.finalized_checkpoint.epoch == spec.GENESIS_EPOCH:
        attested_bid = bid
        spec, state, bid = yield from add_new_block(test, spec, state, num_sync_participants=1)
        yield from select_new_head(test, spec, bid)
        assert (
            get_lc_update_attested_block_id(get_light_client_update_for_period(test, period).data)
            == genesis_bid
        )
        assert (
            get_lc_update_attested_block_id(get_light_client_finality_update(test).data)
            == attested_bid
        )
        assert (
            get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data)
            == attested_bid
        )
    assert state.finalized_checkpoint.epoch == finalized_epoch
    assert state.finalized_checkpoint.root == genesis_bid.root
    assert test.latest_finalized_epoch == finalized_epoch
    assert test.latest_finalized_bid == genesis_bid
    attested_bid = bid

    # Light client data uses the genesis block as `finalized_header`
    spec, state, bid = yield from add_new_block(test, spec, state, num_sync_participants=2)
    yield from select_new_head(test, spec, bid)
    genesis_header = spec.block_to_light_client_header(genesis_block)
    update = get_light_client_update_for_period(test, period).data
    assert get_lc_update_attested_block_id(update) == attested_bid
    assert update.finalized_header == genesis_header
    finality_update = get_light_client_finality_update(test).data
    assert get_lc_update_attested_block_id(finality_update) == attested_bid
    assert finality_update.finalized_header == genesis_header

    # Light client accepts the genesis block as `finalized_header`
    bootstrap = get_light_client_bootstrap(test, genesis_bid.root).data
    store = spec.initialize_light_client_store(genesis_bid.root, bootstrap)
    spec.process_light_client_update(store, update, state.slot, state.genesis_validators_root)
    assert store.best_valid_update == update

    # Finalize the next epoch, which has a different checkpoint block
    while state.finalized_checkpoint.epoch == finalized_epoch:
        attested_bid = bid
        spec, state, bid = yield from add_new_block(test, spec, state, num_sync_participants=2)
        yield from select_new_head(test, spec, bid)
        assert get_light_client_update_for_period(test, period).data == update
        finality_update = get_light_client_finality_update(test).data
        assert get_lc_update_attested_block_id(finality_update) == attested_bid
        assert finality_update.finalized_header == genesis_header
        assert (
            get_lc_update_attested_block_id(get_light_client_optimistic_update(test).data)
            == attested_bid
        )
    finalized_root = state.finalized_checkpoint.root
    assert finalized_root != genesis_bid.root
    bootstrap = get_light_client_bootstrap(test, finalized_root).data
    spec.initialize_light_client_store(finalized_root, bootstrap)

    # Finish test
    yield from finish_lc_data_collection_test(test)
