from eth2spec.test.context import (
    spec_state_test_with_matching_config,
    with_config_overrides,
    with_light_client,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)
from eth2spec.test.helpers.light_client import (
    sample_blob_schedule,
)
from eth2spec.test.helpers.light_client_data_collection import (
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
@spec_state_test_with_matching_config
@with_config_overrides(
    {
        "BLOB_SCHEDULE": sample_blob_schedule(initial_epoch=1, interval=1),
    },
    emit=False,
)
@with_presets([MINIMAL], reason="too slow")
def test_light_client_data_collection(spec, state):
    # Start test
    test = yield from setup_lc_data_collection_test(spec, state)

    # Genesis block is post Altair and is finalized, so can be used as bootstrap
    genesis_bid = BlockID(
        slot=state.slot, root=spec.BeaconBlock(state_root=state.hash_tree_root()).hash_tree_root()
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
    for i in range(1, spec_a.SLOTS_PER_EPOCH):
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
    for i in range(1, spec_a.SLOTS_PER_EPOCH):
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

    # Finish test
    yield from finish_lc_data_collection_test(test)
