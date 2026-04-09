from eth_consensus_specs.test.context import (
    default_activation_threshold,
    default_balances,
    MINIMAL,
    single_phase,
    spec_test,
    with_custom_state,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    FCRTest,
)

"""
Test empty slots
"""


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_handles_single_empty_slot(spec, state):
    """
    Test that FCR correctly handles a single empty slot.

    1. Build chain with full participation for several slots
    2. Skip one slot (no block proposed)
    3. Resume with blocks and attestations
    4. Verify:
       - Confirmations don't spuriously reset
       - slot head variables update correctly across empty slot
       - Chain continues normally and confirmations advance after empty slot
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    # Build normally for first few slots
    fcr.run_slots_with_blocks_and_fast_confirmation(number_of_slots=4, participation_rate=100)

    confirmed_before_empty = fcr_store.confirmed_root
    head_before_empty = fcr.head()

    # With 100% participation, head should be confirmed
    assert confirmed_before_empty == head_before_empty

    # Empty slot: advance time but don't propose a block
    fcr.attest_and_next_slot_with_fast_confirmation(
        block_root=head_before_empty, participation_rate=100
    )

    # Verify head unchanged (no new block)
    assert fcr.head() == head_before_empty, "Head should not change during empty slot"

    # Verify slot head variables still updated
    assert fcr_store.current_slot_head == head_before_empty

    # Confirmed should stay at head_before_empty (no reset)
    assert fcr_store.confirmed_root == head_before_empty, (
        "confirmed_root should stay at head_before_empty during empty slot"
    )

    # Resume normal operation: propose block after empty slot
    block_after_empty = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=head_before_empty, graffiti="after_empty", participation_rate=100
    )

    # This block skips a slot, so parent_block.slot + 1 < block.slot
    parent_slot = store.blocks[head_before_empty].slot
    block_slot = store.blocks[block_after_empty].slot
    assert parent_slot + 1 < block_slot, "Block should have skipped a slot"
    assert fcr.head() == block_after_empty

    # Continue for one more slot to let confirmations advance
    next_block = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=block_after_empty, graffiti="next_block", participation_rate=100
    )

    # Verify expected final state
    assert fcr.head() == next_block
    assert fcr_store.confirmed_root == next_block, "confirmed_root should be next_block"

    yield from fcr.get_test_artefacts()


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
# Note: The exact timing of when confirmation catches up after empty slots
# depends on the validator set size due to how attestation weight accumulates
# across different committee sizes. With 64 validators and 3 empty slots,
# confirmation catches up at the second block after resuming.
def test_fcr_handles_multiple_consecutive_empty_slots(spec, state):
    """
    Test that FCR correctly handles multiple consecutive empty slots.

    1. Build chain with full participation
    2. Skip 3 consecutive slots
    3. Resume with blocks
    4. Verify confirmations still work correctly
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    # Build normally for first few slots
    fcr.run_slots_with_blocks_and_fast_confirmation(number_of_slots=4, participation_rate=100)

    head_before_empty = fcr.head()
    confirmed_before_empty = fcr_store.confirmed_root

    # With 100% participation, head should be confirmed
    assert confirmed_before_empty == head_before_empty

    # 3 consecutive empty slots
    num_empty_slots = 3
    for _ in range(num_empty_slots):
        fcr.attest_and_next_slot_with_fast_confirmation(
            block_root=head_before_empty, participation_rate=100
        )

        # Head unchanged, confirmed stays at head_before_empty
        assert fcr.head() == head_before_empty
        assert fcr_store.confirmed_root == head_before_empty

    # Resume: propose block that skips multiple slots
    block_after_empty = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=head_before_empty, graffiti="after_3_empty", participation_rate=100
    )

    parent_slot = store.blocks[head_before_empty].slot
    block_slot = store.blocks[block_after_empty].slot
    assert block_slot - parent_slot == num_empty_slots + 1, (
        f"Block should skip {num_empty_slots} slots"
    )
    assert fcr.head() == block_after_empty

    # Second block - confirmation catches up
    second_block = fcr.next_slot_with_block_and_fast_confirmation(
        parent_root=block_after_empty, graffiti="second_block", participation_rate=100
    )

    # Verify expected final state
    assert fcr.head() == second_block
    assert fcr_store.confirmed_root == second_block

    yield from fcr.get_test_artefacts()


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_empty_slot_at_epoch_boundary(spec, state):
    """
    Test that FCR correctly handles an empty slot at the epoch boundary.

    The last slot of an epoch is when the GU snapshot is taken. If this slot
    is empty, the snapshot should still occur correctly. The rotation of
    observed checkpoints happens at the first slot of the next epoch.

    1. Build chain through most of epoch 0
    2. Make the last slot of epoch 0 empty (slot 7)
    3. Cross into epoch 1 with blocks
    4. Verify:
       - GU snapshot taken correctly at the empty last slot
       - Observed checkpoints do NOT rotate at the last slot
       - Observed checkpoints DO rotate at epoch 1 start
       - No spurious resets
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    last_slot_epoch0 = S - 1
    epoch1_start = S

    # Build until we're at slot 6 (one before last slot of epoch 0)
    while fcr.current_slot() < last_slot_epoch0 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_epoch0 - 1  # slot 6

    head_before_empty = fcr.head()
    confirmed_before_empty = fcr_store.confirmed_root
    current_observed_before = fcr_store.current_epoch_observed_justified_checkpoint
    previous_observed_before = fcr_store.previous_epoch_observed_justified_checkpoint

    # With 100% participation, head should be confirmed
    assert confirmed_before_empty == head_before_empty

    # Attest at slot 6, then advance to slot 7 (last slot of epoch 0) - EMPTY
    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()

    assert fcr.current_slot() == last_slot_epoch0  # slot 7
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), (
        "Should be last slot of epoch (GU snapshot slot)"
    )

    # Run FCR at slot 7 (empty slot) - this triggers GU snapshot
    fcr.run_fast_confirmation()

    # GU snapshot should have been taken
    assert (
        fcr_store.previous_epoch_greatest_unrealized_checkpoint
        == store.unrealized_justified_checkpoint
    ), "GU snapshot should be taken at last slot of epoch even during empty slot"

    # Observed checkpoints should NOT have rotated (PR #25 fix)
    assert fcr_store.current_epoch_observed_justified_checkpoint == current_observed_before, (
        "current_epoch_observed should NOT change at last slot of epoch"
    )
    assert fcr_store.previous_epoch_observed_justified_checkpoint == previous_observed_before, (
        "previous_epoch_observed should NOT change at last slot of epoch"
    )

    # Head unchanged (empty slot), confirmed stays the same
    assert fcr.head() == head_before_empty
    assert fcr_store.confirmed_root == head_before_empty

    # Record values before crossing into epoch 1
    gu_snapshot = fcr_store.previous_epoch_greatest_unrealized_checkpoint
    curr_observed_before_rotation = fcr_store.current_epoch_observed_justified_checkpoint

    # Attest at slot 7, then cross into epoch 1 (slot 8) WITH A BLOCK
    fcr.attest_and_next_slot_with_fast_confirmation(
        block_root=head_before_empty, participation_rate=100
    )

    assert fcr.current_slot() == epoch1_start  # slot 8
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Rotation should have happened at epoch start
    assert (
        fcr_store.previous_epoch_observed_justified_checkpoint == curr_observed_before_rotation
    ), "previous_observed should now equal old current_observed after rotation at epoch start"
    assert fcr_store.current_epoch_observed_justified_checkpoint == gu_snapshot, (
        "current_observed should now equal GU snapshot after rotation at epoch start"
    )

    # Propose block at epoch 1 start
    first_block_epoch1 = fcr.add_and_apply_block(
        parent_root=head_before_empty, graffiti="first_epoch1"
    )
    fcr.attest(block_root=first_block_epoch1, slot=fcr.current_slot(), participation_rate=100)

    assert fcr.head() == first_block_epoch1
    # Confirmed hasn't caught up yet
    assert fcr_store.confirmed_root == head_before_empty

    # Continue to next slot
    fcr.next_slot()
    fcr.run_fast_confirmation()

    # Second block
    second_block = fcr.add_and_apply_block(parent_root=first_block_epoch1, graffiti="second_block")
    fcr.attest(block_root=second_block, slot=fcr.current_slot(), participation_rate=100)

    assert fcr.head() == second_block
    # Confirmed still hasn't caught up
    assert fcr_store.confirmed_root == head_before_empty

    # Apply attestations for second block
    fcr.next_slot()
    fcr.run_fast_confirmation()

    # Note: The exact timing of when confirmation catches up after an empty slot
    # depends on the validator set size. With 64 validators and one empty slot at
    # the epoch boundary, confirmation catches up after the second block's
    # attestations are applied.
    assert fcr.head() == second_block
    assert fcr_store.confirmed_root == second_block

    yield from fcr.get_test_artefacts()


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_empty_slots_at_epoch_boundary_both_sides(spec, state):
    """
    Test that FCR correctly handles empty slots on both sides of an epoch boundary.

    Both the last slot of epoch 0 AND the first slot of epoch 1 are empty.
    This tests the two-step mechanism:
    - GU snapshot at empty last slot of epoch (no rotation)
    - Rotation at empty first slot of new epoch
    - Interaction between these two critical moments

    1. Build chain through epoch 0 until slot 5
    2. Slot 6, 7 (last of epoch 0): EMPTY - GU snapshot taken at slot 7
    3. Slot 8 (first of epoch 1): EMPTY - rotation happens here
    4. Slot 9: first block of epoch 1
    5. Verify:
       - GU snapshot taken correctly at slot 7
       - Observed checkpoints NOT rotated at slot 7
       - Observed checkpoints rotated at slot 8
       - No spurious resets
       - Confirmations continue after resuming blocks
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    last_slot_epoch0 = S - 1  # slot 7 in MINIMAL
    epoch1_start = S  # slot 8

    # Build until we're at slot 6
    while fcr.current_slot() < last_slot_epoch0 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == last_slot_epoch0 - 1  # slot 6

    head_before_empty = fcr.head()
    head_slot = store.blocks[head_before_empty].slot
    assert head_slot == 5, f"Last block should be at slot 5, got {head_slot}"

    current_observed_before = fcr_store.current_epoch_observed_justified_checkpoint
    previous_observed_before = fcr_store.previous_epoch_observed_justified_checkpoint

    # Slot 6: EMPTY
    fcr.attest_and_next_slot_with_fast_confirmation(
        block_root=head_before_empty, participation_rate=100
    )
    assert fcr.current_slot() == last_slot_epoch0  # slot 7

    # Slot 7: Last slot of epoch 0 (EMPTY) - GU snapshot happens here
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), (
        "Slot 7 should be last slot of epoch 0"
    )

    # GU snapshot should have been taken
    assert (
        fcr_store.previous_epoch_greatest_unrealized_checkpoint
        == store.unrealized_justified_checkpoint
    ), "GU snapshot should be taken at last slot of epoch"

    # Observed checkpoints should NOT have rotated (PR #25)
    assert fcr_store.current_epoch_observed_justified_checkpoint == current_observed_before, (
        "current_epoch_observed should NOT change at last slot of epoch"
    )
    assert fcr_store.previous_epoch_observed_justified_checkpoint == previous_observed_before, (
        "previous_epoch_observed should NOT change at last slot of epoch"
    )

    assert fcr.head() == head_before_empty

    # Record values before crossing into epoch 1
    gu_snapshot = fcr_store.previous_epoch_greatest_unrealized_checkpoint
    curr_observed_before_rotation = fcr_store.current_epoch_observed_justified_checkpoint

    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)

    # Slot 8: First slot of epoch 1 (EMPTY) - rotation happens here
    fcr.next_slot()

    assert fcr.current_slot() == epoch1_start  # slot 8
    assert spec.is_start_slot_at_epoch(fcr.current_slot()), "Slot 8 should be first slot of epoch 1"

    fcr.run_fast_confirmation()

    assert fcr.head() == head_before_empty

    # Rotation should have happened at epoch start
    assert (
        fcr_store.previous_epoch_observed_justified_checkpoint == curr_observed_before_rotation
    ), "previous_observed should now equal old current_observed after rotation at epoch start"
    assert fcr_store.current_epoch_observed_justified_checkpoint == gu_snapshot, (
        "current_observed should now equal GU snapshot after rotation at epoch start"
    )

    # Slot 8: Attest and move to Slot 9
    fcr.attest_and_next_slot_with_fast_confirmation(
        block_root=head_before_empty, participation_rate=100
    )

    # Slot 9: Resume with a block
    assert fcr.current_slot() == epoch1_start + 1  # slot 9

    block_after_empty = fcr.add_and_apply_block(
        parent_root=head_before_empty, graffiti="first_epoch1_block"
    )

    # Verify block skipped 3 empty slots (6, 7, 8)
    parent_slot = store.blocks[head_before_empty].slot
    block_slot = store.blocks[block_after_empty].slot
    assert parent_slot == 5
    assert block_slot == 9
    assert block_slot - parent_slot == 4, (
        f"Block should skip 3 empty slots: parent={parent_slot}, block={block_slot}"
    )

    # Block crosses epoch boundary
    parent_epoch = spec.compute_epoch_at_slot(parent_slot)
    block_epoch = spec.compute_epoch_at_slot(block_slot)
    assert parent_epoch == spec.Epoch(0)
    assert block_epoch == spec.Epoch(1)

    fcr.attest_and_next_slot_with_fast_confirmation(
        block_root=block_after_empty, participation_rate=100
    )
    assert fcr.head() == block_after_empty

    yield from fcr.get_test_artefacts()


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_slot_head_tracking_during_empty_slots(spec, state):
    """
    Test that previous_slot_head and current_slot_head are correctly tracked
    during empty slots.

    Even without new blocks, the slot head variables should update each slot
    to track what the head was at slot start.

    1. Build chain with blocks
    2. Have several empty slots
    3. Verify slot head variables update correctly each slot
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    # Build a few blocks
    fcr.run_slots_with_blocks_and_fast_confirmation(number_of_slots=3, participation_rate=100)

    last_block_head = fcr.head()

    # Track slot heads during empty slots
    slot_head_history = []

    for _ in range(4):  # 4 empty slots
        curr_head_before = fcr_store.current_slot_head
        fcr.attest_and_next_slot_with_fast_confirmation(
            block_root=last_block_head, participation_rate=100
        )

        slot_head_history.append(
            {
                "slot": int(fcr.current_slot()),
                "previous_slot_head": fcr_store.previous_slot_head,
                "current_slot_head": fcr_store.current_slot_head,
                "head": fcr.head(),
            }
        )

        # During empty slots, head doesn't change
        assert fcr.head() == last_block_head

        # current_slot_head should equal head (which is unchanged)
        assert fcr_store.current_slot_head == last_block_head

        # previous_slot_head should equal what current_slot_head was before update
        assert fcr_store.previous_slot_head == curr_head_before

    # All slot heads should point to the same block during empty slots
    for record in slot_head_history:
        assert record["current_slot_head"] == last_block_head
        assert record["previous_slot_head"] == last_block_head
        assert record["head"] == last_block_head

    yield from fcr.get_test_artefacts()
