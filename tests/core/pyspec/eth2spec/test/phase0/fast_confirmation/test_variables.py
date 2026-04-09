from eth2spec.test.context import (
    default_activation_threshold,
    default_balances,
    MINIMAL,
    single_phase,
    spec_test,
    with_altair_and_later,
    with_custom_state,
    with_presets,
)
from eth2spec.test.helpers.fast_confirmation import (
    FCRTest,
)

"""
Test on update FCR variables
"""


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_invariants_monotone_and_canonical(spec, state):
    """
    Validates two critical properties of the Fast Confirmation Rule:
    1. **Monotonicity**: Once a block at slot N is confirmed, all subsequent
       confirmed blocks must be at slots > N (confirmation slot never decreases)
    2. **Canonicality**: The confirmation chain must be a proper subchain of
       the head chain, ensuring confirmed blocks are always canonical
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    prev_confirmed_slot = store.blocks[fcr_store.confirmed_root].slot

    # Run through an entire epoch + 1 to cross epoch boundary
    # This tests reconfirmation and restart logic
    for _ in range(spec.SLOTS_PER_EPOCH + 1):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        head = fcr.head()
        confirmed = fcr_store.confirmed_root

        # Invariant 1: confirmed must be on canonical chain
        assert spec.is_ancestor(store, head, confirmed)

        # Invariant 2: confirmed slot monotonic unless reset to finalized
        confirmed_slot = store.blocks[confirmed].slot

        assert confirmed_slot >= prev_confirmed_slot, (
            f"Confirmed slot went backwards: {prev_confirmed_slot} -> {confirmed_slot}"
        )

        prev_confirmed_slot = confirmed_slot

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_checkpoints_update_timing(spec, state):
    """
    Test the timing of observed justified checkpoint updates:

    1. At genesis, both current_epoch_observed_justified_checkpoint and
       previous_epoch_observed_justified_checkpoint equal the anchor checkpoint
    2. At the last slot of epoch e, only the GU snapshot is taken:
       previous_epoch_greatest_unrealized_checkpoint := unrealized_justified_checkpoint
       (observed checkpoints do NOT rotate yet)
    3. At the first slot of epoch e+1, observed checkpoints ARE rotated:
       previous_epoch_observed := current_epoch_observed
       current_epoch_observed := previous_epoch_greatest_unrealized_checkpoint
    4. During other mid-epoch slots, nothing changes
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # 1. Check initial state at genesis
    anchor_root = store.finalized_checkpoint.root
    anchor_epoch = store.finalized_checkpoint.epoch

    assert fcr_store.previous_epoch_observed_justified_checkpoint.root == anchor_root
    assert fcr_store.previous_epoch_observed_justified_checkpoint.epoch == anchor_epoch
    assert fcr_store.current_epoch_observed_justified_checkpoint.root == anchor_root
    assert fcr_store.current_epoch_observed_justified_checkpoint.epoch == anchor_epoch

    # Run through epochs 0 and 1 to get to epoch 2
    while fcr.current_slot() < 2 * S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == 2 * S  # First slot of epoch 2

    # 2. Check mid-epoch slots don't update observed checkpoints
    # Record values at start of epoch 2 (rotation just happened here)
    prev_at_epoch2_start = fcr_store.previous_epoch_observed_justified_checkpoint
    curr_at_epoch2_start = fcr_store.current_epoch_observed_justified_checkpoint

    # Run through mid-epoch slots of epoch 2 (not last slot, not first slot of next epoch)
    last_slot_of_epoch2 = 3 * S - 1
    while fcr.current_slot() < last_slot_of_epoch2 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # Should NOT be either a GU sampling slot or an epoch start
        assert not spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot())), (
            f"Slot {fcr.current_slot()} should not be an epoch start"
        )
        assert not spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), (
            f"Slot {fcr.current_slot()} should not be the last slot of an epoch"
        )

        # Observed checkpoints should NOT have changed
        assert fcr_store.previous_epoch_observed_justified_checkpoint == prev_at_epoch2_start, (
            f"previous_epoch_observed changed at mid-epoch slot {fcr.current_slot()}"
        )
        assert fcr_store.current_epoch_observed_justified_checkpoint == curr_at_epoch2_start, (
            f"current_epoch_observed changed at mid-epoch slot {fcr.current_slot()}"
        )

    # 3. Check last slot of epoch 2: GU snapshot taken, but NO rotation of observed checkpoints
    assert fcr.current_slot() == last_slot_of_epoch2 - 1

    # Record state before the last slot
    prev_before_last_slot = fcr_store.previous_epoch_observed_justified_checkpoint
    curr_before_last_slot = fcr_store.current_epoch_observed_justified_checkpoint

    # Advance to last slot of epoch 2
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_of_epoch2
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), (
        f"Slot {fcr.current_slot()} should be the last slot of the epoch"
    )

    # After last slot: GU snapshot is taken into previous_epoch_greatest_unrealized_checkpoint
    assert (
        fcr_store.previous_epoch_greatest_unrealized_checkpoint
        == store.unrealized_justified_checkpoint
    ), "previous_epoch_greatest_unrealized_checkpoint should snapshot unrealized at last slot"

    # But observed checkpoints should NOT have rotated yet
    assert fcr_store.previous_epoch_observed_justified_checkpoint == prev_before_last_slot, (
        "previous_epoch_observed should NOT change at last slot of epoch"
    )
    assert fcr_store.current_epoch_observed_justified_checkpoint == curr_before_last_slot, (
        "current_epoch_observed should NOT change at last slot of epoch"
    )

    # 4. Check first slot of epoch 3: NOW the rotation happens
    # Record the snapshot and current_observed before crossing the boundary
    gu_snapshot = fcr_store.previous_epoch_greatest_unrealized_checkpoint
    curr_before_epoch_start = fcr_store.current_epoch_observed_justified_checkpoint

    # Advance to first slot of epoch 3
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    first_slot_of_epoch3 = 3 * S
    assert fcr.current_slot() == first_slot_of_epoch3
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot())), (
        f"Slot {fcr.current_slot()} should be the first slot of the epoch"
    )

    # After epoch start: observed checkpoints rotate
    # previous_observed := old current_observed
    assert fcr_store.previous_epoch_observed_justified_checkpoint == curr_before_epoch_start, (
        "previous_epoch_observed should now equal what current_epoch_observed was before rotation"
    )
    # current_observed := the GU snapshot taken at the last slot of the previous epoch
    assert fcr_store.current_epoch_observed_justified_checkpoint == gu_snapshot, (
        "current_epoch_observed should now equal the GU snapshot from last slot of previous epoch"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_checkpoints_properties_across_epochs(spec, state):
    """

    1. At the last slot of epoch e, the GU snapshot is taken:
       previous_epoch_greatest_unrealized_checkpoint := unrealized_justified_checkpoint
    2. At the first slot of epoch e+1, observed checkpoints rotate:
       previous_observed := current_observed
       current_observed := previous_epoch_greatest_unrealized_checkpoint
    3. Observed checkpoint epochs never decrease under full participation
    4. The cascade holds: previous_observed at epoch e+1 start ==
       current_observed at epoch e start
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    prev_current_observed_epoch = fcr_store.current_epoch_observed_justified_checkpoint.epoch
    prev_previous_observed_epoch = fcr_store.previous_epoch_observed_justified_checkpoint.epoch

    # Records sampled at the first slot of each epoch (where rotation happens)
    observed_at_epoch_start = []

    for epoch in range(4):  # Run through epochs 0, 1, 2, 3
        last_slot = (epoch + 1) * S - 1
        first_slot_next_epoch = (epoch + 1) * S

        # Run to last slot of this epoch
        while fcr.current_slot() < last_slot:
            fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

            # Observed checkpoint epochs never decrease under full participation
            current_observed_epoch = fcr_store.current_epoch_observed_justified_checkpoint.epoch
            previous_observed_epoch = fcr_store.previous_epoch_observed_justified_checkpoint.epoch

            assert current_observed_epoch >= prev_current_observed_epoch, (
                f"current_epoch_observed went backwards: "
                f"{prev_current_observed_epoch} -> {current_observed_epoch}"
            )
            assert previous_observed_epoch >= prev_previous_observed_epoch, (
                f"previous_epoch_observed went backwards: "
                f"{prev_previous_observed_epoch} -> {previous_observed_epoch}"
            )

            prev_current_observed_epoch = current_observed_epoch
            prev_previous_observed_epoch = previous_observed_epoch

        # Now at last slot of epoch — verify GU snapshot is taken
        assert fcr.current_slot() == last_slot
        assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1))

        assert (
            fcr_store.previous_epoch_greatest_unrealized_checkpoint
            == store.unrealized_justified_checkpoint
        ), f"At epoch {epoch} last slot: GU snapshot != unrealized"

        # Record the GU snapshot and current_observed before rotation
        gu_snapshot = fcr_store.previous_epoch_greatest_unrealized_checkpoint
        curr_observed_before_rotation = fcr_store.current_epoch_observed_justified_checkpoint

        # Advance to first slot of next epoch — rotation happens here
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        assert fcr.current_slot() == first_slot_next_epoch
        assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot()))

        # Verify rotation happened correctly
        assert (
            fcr_store.previous_epoch_observed_justified_checkpoint == curr_observed_before_rotation
        ), f"At epoch {epoch + 1} start: previous_observed != old current_observed"
        assert fcr_store.current_epoch_observed_justified_checkpoint == gu_snapshot, (
            f"At epoch {epoch + 1} start: current_observed != GU snapshot from last slot"
        )

        # Monotonicity check continues through epoch start
        current_observed_epoch = fcr_store.current_epoch_observed_justified_checkpoint.epoch
        previous_observed_epoch = fcr_store.previous_epoch_observed_justified_checkpoint.epoch

        assert current_observed_epoch >= prev_current_observed_epoch, (
            f"current_epoch_observed went backwards at epoch start: "
            f"{prev_current_observed_epoch} -> {current_observed_epoch}"
        )
        assert previous_observed_epoch >= prev_previous_observed_epoch, (
            f"previous_epoch_observed went backwards at epoch start: "
            f"{prev_previous_observed_epoch} -> {previous_observed_epoch}"
        )

        prev_current_observed_epoch = current_observed_epoch
        prev_previous_observed_epoch = previous_observed_epoch

        # Record state at epoch start for cascade check
        observed_at_epoch_start.append(
            {
                "epoch": epoch + 1,
                "previous_observed": fcr_store.previous_epoch_observed_justified_checkpoint,
                "current_observed": fcr_store.current_epoch_observed_justified_checkpoint,
                "previous_observed_epoch": int(previous_observed_epoch),
                "current_observed_epoch": int(current_observed_epoch),
            }
        )

    # at epoch e+1 start, previous_observed should equal
    # what current_observed was at epoch e start
    for i in range(1, len(observed_at_epoch_start)):
        prev_record = observed_at_epoch_start[i - 1]
        curr_record = observed_at_epoch_start[i]

        assert curr_record["previous_observed"] == prev_record["current_observed"], (
            f"Cascade broken at epoch {curr_record['epoch']} start: "
            f"previous_observed={curr_record['previous_observed_epoch']} "
            f"but prior current_observed was {prev_record['current_observed_epoch']}"
        )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_stalls_under_low_participation(spec, state):
    """
    Test that observed justified checkpoints stall (don't advance) under low participation.

    With participation below 2/3, FFG justification cannot occur, so:
    - unrealized_justified_checkpoint stays at genesis
    - current_epoch_observed stays at genesis (sampling a stale unrealized)
    - previous_epoch_observed stays at genesis
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    genesis_epoch = fcr_store.current_epoch_observed_justified_checkpoint.epoch

    # Run 3 epochs with very low participation (20%)
    for _ in range(3 * S):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=20)

    # With 20% participation, justification should not occur
    # Therefore observed checkpoints should still be at genesis
    assert fcr_store.current_epoch_observed_justified_checkpoint.epoch == genesis_epoch, (
        f"current_epoch_observed advanced despite low participation: {fcr_store.current_epoch_observed_justified_checkpoint.epoch}"
    )
    assert fcr_store.previous_epoch_observed_justified_checkpoint.epoch == genesis_epoch, (
        f"previous_epoch_observed advanced despite low participation: {fcr_store.previous_epoch_observed_justified_checkpoint.epoch}"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_slot_head_variables_updated_every_slot(spec, state):
    """
    Test that previous_slot_head and current_slot_head are updated every slot.

    Unlike the observed justified checkpoints (which only update at epoch boundaries),
    the slot head variables update on EVERY call to update_fast_confirmation_variables:
        previous_slot_head = current_slot_head
        current_slot_head = get_head(store)
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    curr_slot_head_before = fcr_store.current_slot_head

    # Run several slots and verify the cascade happens each slot
    for i in range(S + 2):  # Run past one epoch boundary
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # After each slot, previous should equal what current was before
        # and current should equal the new head
        expected_previous = curr_slot_head_before
        actual_previous = fcr_store.previous_slot_head
        actual_current = fcr_store.current_slot_head
        actual_head = fcr.head()

        assert actual_previous == expected_previous, (
            f"Slot {fcr.current_slot()}: previous_slot_head cascade failed"
        )
        assert actual_current == actual_head, (
            f"Slot {fcr.current_slot()}: current_slot_head != get_head()"
        )

        # Update tracking for next iteration
        curr_slot_head_before = actual_current

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_gu_snapshot_initialization_and_stability(spec, state):
    """
    Test properties of previous_epoch_greatest_unrealized_checkpoint:

    1. At genesis, it equals the anchor checkpoint (same as other observed variables)
    2. It is only updated at the last slot of an epoch (GU sampling moment)
    3. Between the snapshot (last slot of epoch e) and the rotation (first slot
       of epoch e+1), the snapshot value remains stable even if
       unrealized_justified_checkpoint changes due to epoch processing
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # 1. Check initialization — should equal anchor checkpoint at genesis
    anchor_checkpoint = store.finalized_checkpoint
    assert fcr_store.previous_epoch_greatest_unrealized_checkpoint == anchor_checkpoint, (
        "previous_epoch_greatest_unrealized_checkpoint should equal anchor at genesis"
    )

    # Run through epoch 0 into epoch 1
    while fcr.current_slot() < S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Now at first slot of epoch 1 — run mid-epoch and verify snapshot doesn't change
    gu_snapshot_after_epoch0 = fcr_store.previous_epoch_greatest_unrealized_checkpoint

    last_slot_of_epoch1 = 2 * S - 1
    while fcr.current_slot() < last_slot_of_epoch1 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # 2. Snapshot should NOT change during mid-epoch slots
        assert (
            fcr_store.previous_epoch_greatest_unrealized_checkpoint == gu_snapshot_after_epoch0
        ), f"GU snapshot changed at mid-epoch slot {fcr.current_slot()}"

    # Advance to last slot of epoch 1 — new snapshot is taken
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == last_slot_of_epoch1

    # 3. Snapshot should now reflect the current unrealized_justified_checkpoint
    snapshot_at_last_slot = fcr_store.previous_epoch_greatest_unrealized_checkpoint
    assert snapshot_at_last_slot == store.unrealized_justified_checkpoint, (
        "GU snapshot should equal unrealized at last slot of epoch"
    )

    # Record snapshot before crossing into next epoch
    snapshot_before_epoch_start = fcr_store.previous_epoch_greatest_unrealized_checkpoint

    # Advance to first slot of epoch 2 — epoch processing may advance unrealized
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == 2 * S

    # The rotation should use the snapshot value, NOT the (possibly updated) unrealized
    assert fcr_store.current_epoch_observed_justified_checkpoint == snapshot_before_epoch_start, (
        "Rotation should use the GU snapshot, not the live unrealized_justified_checkpoint"
    )

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_stable_during_last_slot(spec, state):
    """
    At the last slot of an epoch, the observed justified checkpoints used by is_one_confirmed must still
    reflect the old values, not the new ones.

    Concretely: run from epoch start through the entire epoch. Record the
    observed values at the second-to-last slot. Verify they are identical
    at the last slot.

    It verifies that current_epoch_observed_justified_checkpoint and
    previous_epoch_observed_justified_checkpoint have the same value at the
    last slot of the epoch as they did at the first slot
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Run to epoch 2 to have meaningful justified checkpoints
    while fcr.current_slot() < 2 * S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Now at first slot of epoch 2 — record observed checkpoints
    curr_observed_at_epoch_start = fcr_store.current_epoch_observed_justified_checkpoint
    prev_observed_at_epoch_start = fcr_store.previous_epoch_observed_justified_checkpoint

    # Run through the entire epoch, all the way to the last slot
    last_slot_of_epoch2 = 3 * S - 1
    while fcr.current_slot() < last_slot_of_epoch2:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_of_epoch2

    # Observed checkpoints must be the same as at epoch start
    # This is what the old code got wrong — it would have rotated them here
    assert fcr_store.current_epoch_observed_justified_checkpoint == curr_observed_at_epoch_start, (
        "current_epoch_observed must remain stable throughout the entire epoch "
        "(including the last slot)"
    )
    assert fcr_store.previous_epoch_observed_justified_checkpoint == prev_observed_at_epoch_start, (
        "previous_epoch_observed must remain stable throughout the entire epoch "
        "(including the last slot)"
    )

    # But the GU snapshot should have been taken
    assert (
        fcr_store.previous_epoch_greatest_unrealized_checkpoint
        == store.unrealized_justified_checkpoint
    ), "GU snapshot should be taken at last slot even though observed checkpoints don't rotate"

    yield from fcr.get_test_artefacts()
