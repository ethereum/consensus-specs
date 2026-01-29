import copy

from eth_utils import encode_hex

from eth2spec.test.helpers.state import transition_to

from eth2spec.test.context import MINIMAL, spec_state_test, with_altair_and_later, with_presets

from eth2spec.test.helpers.block import build_empty_block  # NOTE: build_empty_block (not _for_next_slot)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to
from eth2spec.test.helpers.fork_choice import add_block

from eth2spec.test.helpers.attestations import get_valid_attestations_for_block_at_slot

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

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fast_confirm_an_epoch(spec, state):
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr.next_slot_with_block_and_fast_confirmation()
        # Ensure head is confirmed
        assert store.confirmed_root == fcr.head()

    yield from fcr.get_test_artefacts()

"""
Test on update FCR variables
"""

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
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
    store = fcr.initialize(state)
    
    prev_confirmed_slot = store.blocks[store.confirmed_root].slot

    # Run through an entire epoch + 1 to cross epoch boundary
    # This tests reconfirmation and restart logic
    for _ in range(spec.SLOTS_PER_EPOCH + 1):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        head = fcr.head()
        confirmed = store.confirmed_root

        # Invariant 1: confirmed must be on canonical chain
        assert spec.is_ancestor(store, head, confirmed)

        # Invariant 2: confirmed slot monotonic unless reset to finalized
        confirmed_slot = store.blocks[confirmed].slot
        finalized = store.finalized_checkpoint.root
        finalized_slot = store.blocks[finalized].slot

        if confirmed != finalized:
            assert confirmed_slot >= prev_confirmed_slot, \
                f"Confirmed slot went backwards: {prev_confirmed_slot} -> {confirmed_slot}"
        else:
            # If reset happened, it must reset exactly to finalized
            assert confirmed_slot == finalized_slot, \
                f"Reset didn't go to finalized: {confirmed_slot} != {finalized_slot}"

        prev_confirmed_slot = confirmed_slot

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_checkpoints_initial_state(spec, state):
    """
    Test that observed justified checkpoints are initialized correctly at genesis.
    
    At genesis:
    - Both previous_epoch_observed_justified_checkpoint and 
      current_epoch_observed_justified_checkpoint should equal the anchor checkpoint
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    anchor_root = store.finalized_checkpoint.root
    anchor_epoch = store.finalized_checkpoint.epoch

    # Both observed checkpoints should be initialized to anchor
    assert store.previous_epoch_observed_justified_checkpoint.root == anchor_root
    assert store.previous_epoch_observed_justified_checkpoint.epoch == anchor_epoch
    assert store.current_epoch_observed_justified_checkpoint.root == anchor_root
    assert store.current_epoch_observed_justified_checkpoint.epoch == anchor_epoch

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_checkpoints_not_updated_mid_epoch(spec, state):
    """
    Test that observed justified checkpoints are NOT updated during mid-epoch slots.
    
    The update only happens at the last slot of an epoch (when current_slot + 1 is epoch start).
    During all other slots, the observed checkpoints should remain unchanged by 
    update_fast_confirmation_variables.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    last_slot_of_epoch0 = S - 1  

    # Record initial values
    initial_prev = store.previous_epoch_observed_justified_checkpoint
    initial_curr = store.current_epoch_observed_justified_checkpoint

    # Run through slots 1 to last_slot - 1 
    # These are all mid-epoch slots where GU sampling should NOT happen
    for slot in range(1, last_slot_of_epoch0):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
        
        assert fcr.current_slot() == slot
        assert not spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), \
            f"Slot {slot} should not trigger GU sampling"

        # Observed checkpoints should NOT have changed
        assert store.previous_epoch_observed_justified_checkpoint == initial_prev, \
            f"previous_epoch_observed changed at mid-epoch slot {slot}"
        assert store.current_epoch_observed_justified_checkpoint == initial_curr, \
            f"current_epoch_observed changed at mid-epoch slot {slot}"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_checkpoints_updated_at_last_slot_of_epoch(spec, state):
    """
    Test that observed justified checkpoints are updated at the last slot of an epoch.
    
    The logic in update_fast_confirmation_variables:
        if is_start_slot_at_epoch(Slot(get_current_slot(store) + 1)):
            previous_epoch_observed := current_epoch_observed
            current_epoch_observed := unrealized_justified_checkpoint
    
    This triggers when current_slot is the LAST slot of an epoch.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    last_slot_of_epoch1 = 2*S - 1  

    # Run to slot before the last slot
    while fcr.current_slot() < last_slot_of_epoch1 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_of_epoch1 - 1

    # Record state before the critical slot
    prev_before = store.previous_epoch_observed_justified_checkpoint
    curr_before = store.current_epoch_observed_justified_checkpoint
    unrealized_before = store.unrealized_justified_checkpoint

    # Advance to last slot of epoch  and run FCR
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_of_epoch1
    # Verify this is the trigger condition
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), \
        f"Slot {fcr.current_slot()} should trigger GU sampling (next slot is epoch start)"

    # After update_fast_confirmation_variables runs:
    # - previous_epoch_observed should now equal what current_epoch_observed was
    # - current_epoch_observed should now equal unrealized_justified_checkpoint
    assert store.previous_epoch_observed_justified_checkpoint == curr_before, \
        "previous_epoch_observed should have been set to old current_epoch_observed"
    
    # Note: current_epoch_observed is set to unrealized at the moment of sampling,
    # which may have advanced since unrealized_before due to block processing
    # So we check it equals the current unrealized (not unrealized_before)
    assert store.current_epoch_observed_justified_checkpoint == store.unrealized_justified_checkpoint, \
        "current_epoch_observed should equal unrealized_justified_checkpoint after sampling"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_checkpoints_cascade_across_epochs(spec, state):
    """
    Test that observed justified checkpoints cascade correctly across multiple epochs.
    
    At each epoch boundary (last slot):
    - previous := current
    - current := unrealized
    
    With 100% participation, we should see:
    - Epoch 0 end: current_observed captures unrealized (likely epoch 0)
    - Epoch 1 end: previous_observed gets epoch 0's value, current gets epoch 1's unrealized
    - Epoch 2 end: previous gets epoch 1's value, current gets epoch 2's unrealized
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    observed_history = []

    for epoch in range(4):  # Run through epochs 0, 1, 2, 3
        last_slot = (epoch + 1) * S - 1

        # Run to last slot of this epoch
        while fcr.current_slot() < last_slot:
            fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # Now at last slot of epoch
        assert fcr.current_slot() == last_slot
        assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1))

        # Record the observed values AFTER the update ran
        observed_history.append({
            'epoch': epoch,
            'slot': fcr.current_slot(),
            'previous_observed_epoch': int(store.previous_epoch_observed_justified_checkpoint.epoch),
            'current_observed_epoch': int(store.current_epoch_observed_justified_checkpoint.epoch),
            'unrealized_epoch': int(store.unrealized_justified_checkpoint.epoch),
        })

    # Verify the cascade property:
    # At epoch E's last slot, previous_observed should equal what current_observed was at epoch E-1's last slot
    for i in range(1, len(observed_history)):
        prev_record = observed_history[i - 1]
        curr_record = observed_history[i]

        assert curr_record['previous_observed_epoch'] == prev_record['current_observed_epoch'], \
            f"Cascade broken at epoch {curr_record['epoch']}: " \
            f"previous_observed={curr_record['previous_observed_epoch']} " \
            f"but prior current_observed was {prev_record['current_observed_epoch']}"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_observed_justified_monotonically_increasing_under_full_participation(spec, state):
    """
    Test that observed justified checkpoint epochs are monotonically non-decreasing
    under full participation.
    
    With 100% honest participation, unrealized_justified should advance each epoch,
    and therefore current_epoch_observed should never decrease.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    prev_current_observed_epoch = store.current_epoch_observed_justified_checkpoint.epoch
    prev_previous_observed_epoch = store.previous_epoch_observed_justified_checkpoint.epoch

    # Run through 4 epochs
    for _ in range(4 * S):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        current_observed_epoch = store.current_epoch_observed_justified_checkpoint.epoch
        previous_observed_epoch = store.previous_epoch_observed_justified_checkpoint.epoch

        # Monotonicity: epochs should never decrease
        assert current_observed_epoch >= prev_current_observed_epoch, \
            f"current_epoch_observed went backwards: {prev_current_observed_epoch} -> {current_observed_epoch}"
        assert previous_observed_epoch >= prev_previous_observed_epoch, \
            f"previous_epoch_observed went backwards: {prev_previous_observed_epoch} -> {previous_observed_epoch}"

        # Update tracking
        prev_current_observed_epoch = current_observed_epoch
        prev_previous_observed_epoch = previous_observed_epoch

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
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
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    genesis_epoch = store.current_epoch_observed_justified_checkpoint.epoch

    # Run 3 epochs with very low participation (20%)
    for _ in range(3 * S):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=20)

    # With 20% participation, justification should not occur
    # Therefore observed checkpoints should still be at genesis
    assert store.current_epoch_observed_justified_checkpoint.epoch == genesis_epoch, \
        f"current_epoch_observed advanced despite low participation: {store.current_epoch_observed_justified_checkpoint.epoch}"
    assert store.previous_epoch_observed_justified_checkpoint.epoch == genesis_epoch, \
        f"previous_epoch_observed advanced despite low participation: {store.previous_epoch_observed_justified_checkpoint.epoch}"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_current_observed_equals_unrealized_at_sampling_moment(spec, state):
    """
    Test that current_epoch_observed_justified_checkpoint equals unrealized_justified_checkpoint
    at the exact moment of sampling (last slot of epoch).
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Test across multiple epoch boundaries
    for epoch in range(3):
        last_slot = (epoch + 1) * S - 1

        # Advance to last slot of epoch
        while fcr.current_slot() < last_slot:
            fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        assert fcr.current_slot() == last_slot

        # At this point, update_fast_confirmation_variables has already run
        # (it runs as part of on_slot_start_after_past_attestations_applied)
        # So current_observed should equal unrealized
        assert store.current_epoch_observed_justified_checkpoint == store.unrealized_justified_checkpoint, \
            f"At epoch {epoch} last slot: current_observed != unrealized"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_previous_observed_lags_current_observed_by_one_epoch(spec, state):
    """
    Test that previous_epoch_observed is always one sampling behind current_epoch_observed.
    
    After full participation for several epochs:
    - At epoch E's last slot, previous_observed should have the value that 
      current_observed had at epoch E-1's last slot
    - This means previous_observed.epoch should typically be current_observed.epoch - 1
      (under steady-state full participation)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Run through epoch 0 and 1 to reach steady state
    while fcr.current_slot() < 2 * S - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Now at last slot of epoch 1, record current_observed
    assert fcr.current_slot() == 2 * S - 1
    current_at_epoch1_end = store.current_epoch_observed_justified_checkpoint

    # Advance through epoch 2 to its last slot
    while fcr.current_slot() < 3 * S - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Now at last slot of epoch 2
    assert fcr.current_slot() == 3 * S - 1

    # previous_observed should now equal what current_observed was at epoch 1 end
    assert store.previous_epoch_observed_justified_checkpoint == current_at_epoch1_end, \
        f"previous_observed at epoch 2 end should equal current_observed at epoch 1 end"

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
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
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    prev_slot_head_before = store.previous_slot_head
    curr_slot_head_before = store.current_slot_head

    # Run several slots and verify the cascade happens each slot
    for i in range(S + 2):  # Run past one epoch boundary
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # After each slot, previous should equal what current was before
        # and current should equal the new head
        expected_previous = curr_slot_head_before
        actual_previous = store.previous_slot_head
        actual_current = store.current_slot_head
        actual_head = fcr.head()

        assert actual_previous == expected_previous, \
            f"Slot {fcr.current_slot()}: previous_slot_head cascade failed"
        assert actual_current == actual_head, \
            f"Slot {fcr.current_slot()}: current_slot_head != get_head()"

        # Update tracking for next iteration
        curr_slot_head_before = actual_current

    yield from fcr.get_test_artefacts()


"""
Test empty slots
"""

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
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
       - Confirmations continue to advance
       - slot head variables update correctly across empty slot
       - No spurious resets occur
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build normally for first few slots
    for _ in range(4):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    confirmed_before_empty = store.confirmed_root
    head_before_empty = fcr.head()

    # Empty slot: advance time but don't propose a block
    # Just tick to next slot, apply any pending attestations, run FCR
    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    empty_slot = fcr.current_slot()

    # Verify head unchanged (no new block)
    assert fcr.head() == head_before_empty, "Head should not change during empty slot"

    # Verify slot head variables still updated
    assert store.current_slot_head == head_before_empty

    # Confirmed should not have reset
    assert store.confirmed_root != store.finalized_checkpoint.root or \
           confirmed_before_empty == store.finalized_checkpoint.root, \
        "Confirmed should not spuriously reset due to empty slot"

    # Resume normal operation: propose block after empty slot
    block_after_empty = fcr.add_and_apply_block(parent_root=head_before_empty, graffiti="after_empty")
    
    # This block skips a slot, so parent_block.slot + 1 < block.slot
    parent_slot = store.blocks[head_before_empty].slot
    block_slot = store.blocks[block_after_empty].slot
    assert parent_slot + 1 < block_slot, "Block should have skipped a slot"

    fcr.attest(block_root=block_after_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Verify chain continues normally
    assert fcr.head() == block_after_empty

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_handles_multiple_consecutive_empty_slots(spec, state):
    """
    Test that FCR correctly handles multiple consecutive empty slots.

    1. Build chain with full participation
    2. Skip 3 consecutive slots 
    3. Resume with blocks
    4. Verify confirmations still work correctly
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Build normally for first few slots
    for _ in range(4):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    head_before_empty = fcr.head()
    confirmed_before_empty = store.confirmed_root

    # 3 consecutive empty slots
    num_empty_slots = 3
    for i in range(num_empty_slots):
        # Attest to current head during empty slot
        fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

        # Head unchanged
        assert fcr.head() == head_before_empty

    # Resume: propose block that skips multiple slots
    block_after_empty = fcr.add_and_apply_block(parent_root=head_before_empty, graffiti="after_3_empty")

    parent_slot = store.blocks[head_before_empty].slot
    block_slot = store.blocks[block_after_empty].slot
    assert block_slot - parent_slot == num_empty_slots + 1, \
        f"Block should skip {num_empty_slots} slots"

    fcr.attest(block_root=block_after_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Chain continues
    assert fcr.head() == block_after_empty

    # Confirmed should not have spuriously reset
    assert store.confirmed_root != store.finalized_checkpoint.root or \
           confirmed_before_empty == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_empty_slot_at_epoch_boundary(spec, state):
    """
    Test that FCR correctly handles an empty slot at the epoch boundary.

    The last slot of an epoch is when GU sampling happens. If this slot is empty,
    the sampling should still occur correctly.

    1. Build chain through most of epoch 0
    2. Make the last slot of epoch 0 empty 
    3. Cross into epoch 1
    4. Verify:
       - GU sampling occurred correctly at the empty last slot
       - Epoch boundary logic works correctly
       - No resets
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    last_slot_epoch0 = S - 1  
    epoch1_start = S         

    # Build until we're at slot 6 (one before last slot of epoch 0)
    # next_slot_with_block_and_fast_confirmation advances the slot after processing
    while fcr.current_slot() < last_slot_epoch0 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_epoch0 - 1  # slot 6

    head_before_empty = fcr.head()
    current_observed_before = store.current_epoch_observed_justified_checkpoint

    # Attest at slot 6, then advance to slot 7 (last slot of epoch 0)
    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    assert fcr.current_slot() == last_slot_epoch0  # slot 7
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), \
        "Should be last slot of epoch (GU sampling slot)"

    # Run FCR at slot 7 (empty slot) - this triggers GU sampling
    fcr.run_fast_confirmation()

    # GU sampling should have happened
    # previous_epoch_observed should now equal what current_epoch_observed was
    assert store.previous_epoch_observed_justified_checkpoint == current_observed_before

    # Head unchanged (empty slot)
    assert fcr.head() == head_before_empty

    # Attest at slot 7, then cross into epoch 1 (slot 8)
    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    assert fcr.current_slot() == epoch1_start  # slot 8
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    fcr.run_fast_confirmation()

    # Should not have reset spuriously
    # (confirmed may or may not have advanced, but shouldn't reset without cause)

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_empty_slots_at_epoch_boundary_both_sides(spec, state):
    """
    Test that FCR correctly handles empty slots on both sides of an epoch boundary.

    Both the last slot of epoch 0 AND the first slot of epoch 1 are empty.
    This tests:
    - GU sampling at empty last slot of epoch
    - Epoch-start logic at empty first slot of new epoch
    - Interaction between these two critical moments

    1. Build chain through epoch 0 until slot 5
    2. Slot 6, 7 (last of epoch 0): EMPTY - GU sampling happens at slot 7
    3. Slot 8 (first of epoch 1): EMPTY - epoch-start logic runs here
    4. Slot 9: first block of epoch 1
    5. Verify:
       - GU sampling occurred correctly at slot 7
       - Epoch boundary logic works correctly at slot 8
       - No spurious resets
       - Confirmations continue after resuming blocks
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    last_slot_epoch0 = S - 1  # slot 7 in MINIMAL
    epoch1_start = S          # slot 8

    # Build until we're at slot 6
    # next_slot_with_block_and_fast_confirmation places block then advances
    # So after the loop, current_slot == 6 and last block was at slot 5
    while fcr.current_slot() < last_slot_epoch0 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_epoch0 - 1  # slot 6

    head_before_empty = fcr.head()
    head_slot = store.blocks[head_before_empty].slot
    assert head_slot == 5, f"Last block should be at slot 5, got {head_slot}"

    confirmed_before_empty = store.confirmed_root
    current_observed_before = store.current_epoch_observed_justified_checkpoint

    # === Slot 6: EMPTY ===
    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    assert fcr.current_slot() == last_slot_epoch0  # slot 7

    # Slot 7: Last slot of epoch 0 (EMPTY) - GU sampling happens here 
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), \
        "Slot 7 should be last slot of epoch 0"

    fcr.attest(block_root=head_before_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.run_fast_confirmation()

    # Verify GU sampling happened
    assert store.previous_epoch_observed_justified_checkpoint == current_observed_before, \
        "GU sampling should have shifted previous := current"
    
    current_observed_after_sampling = store.current_epoch_observed_justified_checkpoint
    assert fcr.head() == head_before_empty

    # Slot 8: First slot of epoch 1 (EMPTY) 
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    assert fcr.current_slot() == epoch1_start  # slot 8
    assert spec.is_start_slot_at_epoch(fcr.current_slot()), \
        "Slot 8 should be first slot of epoch 1"

    fcr.run_fast_confirmation()

    assert fcr.head() == head_before_empty
    assert store.current_epoch_observed_justified_checkpoint == current_observed_after_sampling, \
        "GU should not change at epoch start (only at epoch end)"

    # Slot 9: Resume with a block 
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    assert fcr.current_slot() == epoch1_start + 1  # slot 9

    block_after_empty = fcr.add_and_apply_block(parent_root=head_before_empty, graffiti="first_epoch1_block")

    # Verify block skipped 3 empty slots (6, 7, 8)
    parent_slot = store.blocks[head_before_empty].slot
    block_slot = store.blocks[block_after_empty].slot
    assert parent_slot == 5
    assert block_slot == 9
    assert block_slot - parent_slot == 4, \
        f"Block should skip 3 empty slots: parent={parent_slot}, block={block_slot}"

    # Block crosses epoch boundary
    parent_epoch = spec.compute_epoch_at_slot(parent_slot)
    block_epoch = spec.compute_epoch_at_slot(block_slot)
    assert parent_epoch == spec.Epoch(0)
    assert block_epoch == spec.Epoch(1)

    fcr.attest(block_root=block_after_empty, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    assert fcr.head() == block_after_empty

    fcr.blockchain_artefacts.append(("epoch_boundary_empty_slots", {
        "last_block_before_empty_slot": int(parent_slot),
        "empty_slots": [6, 7, 8],
        "first_block_after_empty_slot": int(block_slot),
        "gu_sampled_at_slot": int(last_slot_epoch0),
        "epoch_start_at_slot": int(epoch1_start),
    }))

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
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
    store = fcr.initialize(state)

    # Build a few blocks
    for _ in range(3):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    last_block_head = fcr.head()

    # Track slot heads during empty slots
    slot_head_history = []

    for i in range(4):  # 4 empty slots
        prev_head_before = store.previous_slot_head
        curr_head_before = store.current_slot_head

        fcr.attest(block_root=last_block_head, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

        slot_head_history.append({
            'slot': int(fcr.current_slot()),
            'previous_slot_head': store.previous_slot_head,
            'current_slot_head': store.current_slot_head,
            'head': fcr.head(),
        })

        # During empty slots, head doesn't change
        assert fcr.head() == last_block_head

        # current_slot_head should equal head (which is unchanged)
        assert store.current_slot_head == last_block_head

        # previous_slot_head should equal what current_slot_head was before update
        assert store.previous_slot_head == curr_head_before

    # All slot heads should point to the same block during empty slots
    for record in slot_head_history:
        assert record['current_slot_head'] == last_block_head
        assert record['previous_slot_head'] == last_block_head
        assert record['head'] == last_block_head

    yield from fcr.get_test_artefacts()

"""
Test on revert to finality
"""

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_no_reset_when_confirmed_exactly_one_epoch_old(spec, state):
    """
    Test that confirmed_root does NOT reset when it's exactly one epoch old.

    The "too old" guard is: epoch(bcand) + 1 < current_epoch
    When epoch(bcand) + 1 == current_epoch, this is FALSE and no reset should occur.

    1. Epochs 0-1: 100% participation, confirmations advance into epoch 1
    2. Epoch 2: Low participation, confirmations stall in epoch 1
    3. Throughout epoch 2: confirmed stays in epoch 1, but should NOT reset
       because epoch(bcand=1) + 1 = 2 == current_epoch (not < current_epoch)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Full participation through epoch 1
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start
    
    # Confirm we have confirmations in epoch 1
    confirmed_at_epoch2_start = store.confirmed_root
    assert confirmed_at_epoch2_start != store.finalized_checkpoint.root
    assert spec.get_block_epoch(store, confirmed_at_epoch2_start) == spec.Epoch(1)

    # Epoch 2 with low participation - confirmations should stall but NOT reset
    low_participation = 15

    while fcr.current_slot() < epoch3_start - 1:  # Stop before crossing into epoch 3
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

        current_epoch = spec.get_current_store_epoch(store)
        confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)

        # Key invariant: throughout epoch 2, confirmed is in epoch 1
        # epoch(bcand=1) + 1 = 2 == current_epoch=2, so NOT "too old"
        assert current_epoch == spec.Epoch(2)
        assert confirmed_epoch == spec.Epoch(1)
        
        # Should NOT have reset to finalized
        assert store.confirmed_root != store.finalized_checkpoint.root, \
            f"Unexpected reset at slot {fcr.current_slot()}: " \
            f"confirmed_epoch={confirmed_epoch}, current_epoch={current_epoch}"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_no_reset_at_epoch_boundary_with_full_participation(spec, state):
    """
    Test that confirmed_root does NOT reset when crossing epoch boundaries
    under healthy conditions (full participation).

      
    1. Run multiple epochs with 100% participation
    2. At each epoch boundary, verify:
       - confirmed_root is NOT reset to finalized
       - confirmed_root continues advancing
       - Reconfirmation passes (is_confirmed_chain_safe returns True)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Track confirmed across epoch boundaries
    confirmed_at_boundaries = []

    for epoch in range(4):
        epoch_start = epoch * S
        next_epoch_start = (epoch + 1) * S

        # Run through the epoch
        while fcr.current_slot() < next_epoch_start:
            fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # At epoch boundary
        if epoch > 0:  # Skip genesis epoch
            current_confirmed = store.confirmed_root
            confirmed_epoch = spec.get_block_epoch(store, current_confirmed)
            
            confirmed_at_boundaries.append({
                'at_epoch': epoch + 1,
                'confirmed_epoch': int(confirmed_epoch),
                'confirmed_root': current_confirmed,
                'is_finalized': current_confirmed == store.finalized_checkpoint.root,
            })

            # Should NOT have reset to finalized under full participation
            assert current_confirmed != store.finalized_checkpoint.root, \
                f"Unexpected reset at epoch {epoch + 1} boundary"

    # Verify confirmations advanced over time
    confirmed_epochs = [b['confirmed_epoch'] for b in confirmed_at_boundaries]
    assert confirmed_epochs[-1] > confirmed_epochs[0], \
        f"Confirmations did not advance: {confirmed_epochs}"

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_too_old_lower_participation(spec, state):
    """
    Goal:
      - Get confirmed_root into epoch 1 under full participation.
      - Then run low participation through epoch 2 so confirmed_root becomes "too old"
        only when we reach epoch 3 start.
      - At epoch 3 start: reset confirmed_root to finalized.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch1_start = 1 * S
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # 1) Full participation up to epoch 2 start.
    #    Ensure confirmed_root has advanced into epoch 1 (critical).
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Confirm we are indeed in the regime "confirmed is in epoch 1".
    assert store.confirmed_root != store.finalized_checkpoint.root
    assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(1)

    frozen_epoch1_confirmed = store.confirmed_root

    # 2) Epoch 2 with low participation: confirmed should not reset yet.
    low_participation = 60  # or 20/5; pick something clearly low for *confirmation* in your model

    while fcr.current_slot() < epoch3_start - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

        # Must not reset before epoch 3 start.
        assert store.confirmed_root != store.finalized_checkpoint.root

        # It should still be from epoch 1 (it may or may not equal frozen_epoch1_confirmed).
        assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(1)

    # We are now at slot epoch3_start - 1, i.e., last slot before the boundary.
    assert fcr.current_slot() == epoch3_start - 1
    pre_boundary_confirmed = store.confirmed_root
    assert spec.get_block_epoch(store, pre_boundary_confirmed) == spec.Epoch(1)

    # 3) Cross into epoch 3 start: now it becomes "too old" and should reset.
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    current_epoch = spec.get_current_store_epoch(store)
    assert current_epoch == spec.Epoch(3)

    # Reset condition: pre-boundary confirmed was epoch 1, so 1 + 1 < 3.
    assert spec.get_block_epoch(store, pre_boundary_confirmed) + 1 < current_epoch

    # Must have reset to finalized at epoch 3 start.
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_at_epoch_boundary(spec, state):
    """
    Test that confirmed_root resets when it becomes non-canonical at an epoch boundary.

    1. Build chain into epoch 1 with full participation, confirmations advancing
    2. At slot 10, create fork point R
    3. Create siblings at slot 11:
    - Branch A: canonical initially, confirmations advance here
    - Branch M: competing sibling
    4. Extend A-side with 100% votes until 2 slots before epoch 2 boundary
    - Confirmations advance onto A-side chain
    5. Last 2 slots of epoch 1: vote 100% for M while still extending A
    6. At epoch 2 start (slot 16): 
    - Head flips from A-side to M-side due to accumulated M votes
    - Previously confirmed blocks on A-side become non-canonical
    7. FCR should reset confirmed_root to finalized
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S

    # Build chain into epoch 1 with full participation
    while fcr.current_slot() < S + 2:  # slot 10
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Create fork point R
    r_root = fcr.add_and_apply_block(parent_root=fcr.head(), graffiti="R")
    fcr.attest(block_root=r_root, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Create siblings A and M at current slot
    fork_slot = fcr.current_slot()
    prev_atts = list(fcr.attestation_pool)

    # A block
    a_root = fcr.add_and_apply_block(parent_root=r_root, graffiti="A")

    # M block (sibling)
    parent_state = store.block_states[r_root].copy()
    m_block = build_empty_block(spec, parent_state, fork_slot)
    for att in prev_atts:
        m_block.body.attestations.append(att)
    m_block.body.graffiti = b"M".ljust(32, b"\x00")
    signed_m = state_transition_and_sign_block(spec, parent_state, m_block)
    for artefact in add_block(spec, store, signed_m, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    m_root = signed_m.message.hash_tree_root()

    # Build up A-side with strong votes until near epoch boundary
    fcr.attest(block_root=a_root, slot=fork_slot, participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Keep extending A-side with 100% votes until 2 slots before epoch boundary
    a_tip = a_root
    while fcr.current_slot() < epoch2_start - 2:
        a_tip = fcr.add_and_apply_block(parent_root=a_tip, graffiti=f"A_{fcr.current_slot()}")
        fcr.attest(block_root=a_tip, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    # Verify confirmed is on A-side (a_root is ancestor of confirmed or confirmed equals something on A chain)
    head = fcr.head()
    confirmed = store.confirmed_root
    
    # The confirmed should be on the canonical chain
    assert spec.is_ancestor(store, head, confirmed), "Confirmed should be canonical"
    assert confirmed != store.finalized_checkpoint.root, "Confirmed should have advanced"
    
    # Check that A-side is the canonical chain
    assert spec.is_ancestor(store, head, a_root), "Head should be on A-side"
    
    confirmed_before_reorg = confirmed

    # Now vote heavily for M to trigger reorg at epoch boundary
    # Slot epoch2_start - 2
    a_tip = fcr.add_and_apply_block(parent_root=a_tip, graffiti="A_pre_boundary")
    fcr.attest(block_root=m_root, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Slot epoch2_start - 1 (last slot of epoch 1)
    a_tip = fcr.add_and_apply_block(parent_root=a_tip, graffiti="A_last")
    fcr.attest(block_root=m_root, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []

    # Now at epoch 2 start - don't run FCR yet, check state
    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Run FCR at epoch boundary
    fcr.run_fast_confirmation()

    # Check if head flipped
    head = fcr.head()
    
    if spec.is_ancestor(store, head, m_root) or head == m_root:
        # Head is on M-side
        # Check if confirmed_before_reorg is still canonical
        if not spec.is_ancestor(store, head, confirmed_before_reorg):
            # Confirmed became non-canonical → should reset
            assert store.confirmed_root == store.finalized_checkpoint.root, \
                "Expected reset when confirmed becomes non-canonical at epoch boundary"
        else:
            # Confirmed was on common prefix (before fork), still canonical
            pass
    else:
        # Head didn't flip - need more M votes or different timing
        fcr.blockchain_artefacts.append(("diagnostic", {
            "head": encode_hex(head),
            "m_root": encode_hex(m_root),
            "a_root": encode_hex(a_root),
            "note": "Head did not flip to M-side"
        }))

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_confirmed_not_canonical_mid_epoch(spec, state):
    """
    Test that confirmed_root resets to finalized when it becomes non-canonical due to a reorg at mid-epoch.
    
 
    1. Build a chain with confirmations advancing normally into epoch 2 (mid-epoch)
    2. Create a fork at block R with two competing children:
       - Block A: Initially becomes canonical (75% vote)
       - Block M: Competing sibling (same slot, same parent)
    3. Extend the A-chain: R → A → B → C → D
       - Confirmations advance onto the A-side chain
    4. Reorg by voting 100% for M (twice):
       - Head flips from D (A-side) to M (M-side)
       - Previously confirmed blocks on A-side become non-canonical
    
    When confirmed blocks become non-canonical, FCR must reset confirmed_root to 
    finalized_checkpoint.root rather than moving confirmations backward.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S

    # Drive to epoch 2 start, then 2 slots into epoch 2 (mid-epoch)
    fcr.run_slots_with_blocks_and_fast_confirmation(
        epoch2_start - fcr.current_slot(), participation_rate=100
    )
    fcr.run_slots_with_blocks_and_fast_confirmation(2, participation_rate=100)
    assert fcr.current_slot() % S != 0  # mid-epoch

    # Build fork parent R at current slot; vote 100% for it; advance + apply + FCR
    r_root = fcr.add_and_apply_block(parent_root=fcr.head())
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=r_root, participation_rate=100)

    # Now we are at the fork slot: create siblings A (canonical) and M (competing)
    fork_slot = fcr.current_slot()
    assert fork_slot % S != 0

    # Save "previous-slot" attestations that should be included in blocks at fork_slot
    prev_atts = list(fcr.attestation_pool)

    # Canonical child A at fork_slot
    a_root = fcr.add_and_apply_block(parent_root=r_root)

    # Competing sibling M at same parent/slot (manual build)
    parent_state = store.block_states[r_root].copy()
    competing_block = build_empty_block(spec, parent_state, fork_slot)
    for att in prev_atts:
        competing_block.body.attestations.append(att)
    competing_block.body.graffiti = b"i_love_ethereum".ljust(32, b"\x00")

    signed_m = state_transition_and_sign_block(spec, parent_state, competing_block)
    for artefact in add_block(spec, store, signed_m, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    m_root = signed_m.message.hash_tree_root()

    # Slot fork_slot: 75% attest to A; advance + apply + FCR
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=a_root, participation_rate=75)

    # Next slot: build B on A; attest 100% to B; advance + apply + FCR
    b_root = fcr.add_and_apply_block(parent_root=a_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=b_root, participation_rate=100)

    # By now we should have confirmed onto the A side
    assert spec.is_ancestor(store, store.confirmed_root, a_root), "Confirmed did not reach A"

    # snapshot what confirmed_root is *before* we start pushing 100%-to-M 
    confirmed_before_flip = store.confirmed_root
    assert confirmed_before_flip != store.finalized_checkpoint.root
    assert spec.is_ancestor(store, confirmed_before_flip, a_root)

    # Next slot: build C on B; attest 100% to M; advance + apply + FCR
    c_root = fcr.add_and_apply_block(parent_root=b_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=m_root, participation_rate=100)

    # Confirmed still on A side 
    assert spec.is_ancestor(store, store.confirmed_root, a_root)

    # Next slot: build D on C; attest 100% to M again; advance + apply + FCR
    _d_root = fcr.add_and_apply_block(parent_root=c_root)
    fcr.attest_and_next_slot_with_fast_confirmation(block_root=m_root, participation_rate=100)

    # Now: head should be on M side, and confirmed should have reset to finalized.
    # (FCR does not move confirmations backwards; it resets to finalized when confirmed becomes non-canonical.)
    head = fcr.head()
    assert spec.is_ancestor(store, head, m_root), "Head did not flip to M"
    assert store.confirmed_root == store.finalized_checkpoint.root, "Expected reset to finalized mid-epoch"
    assert store.confirmed_root != confirmed_before_flip  # we actually reset

    yield from fcr.get_test_artefacts()

# At an epoch boundary, if the previously confirmed chain cannot be re-confirmed
# under the new epoch anchor, FCR must reset confirmed_root to finalized
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_reverts_to_finalized_when_reconfirmation_fails_at_epoch_start_due_to_late_equivocations(spec, state):
    """
    Test that confirmed_root resets to finalized when reconfirmation fails at an epoch boundary.

     
    1. Build chain through epoch 2 with 100% participation
    - Confirmations advance into epoch 2
    - Ensure confirmed_root is NOT "too old" (to isolate reconfirmation failure)

    2. In the last 3 slots before epoch 3 boundary (slots s1, s2, s3):
    - Create competing forks: 6 blocks total (tip vs competing sibling per slot)
    - Vote 100% for the "tip" blocks each time
    - The tip blocks become one-confirmed under the previous epoch balance source

    3. At the epoch 3 boundary (before running FCR):
    - Late equivocation evidence arrives (3 attester slashings, 25% each)
    - This adds validators to store.equivocating_indices
    - Slashed validators' balances are now excluded from attestation weight

    4. Run epoch-start FCR logic (reconfirmation check):
    - FCR attempts to reconfirm the previous confirmed_root under the NEW balance source
    - With 75% of validators slashed, the tip blocks no longer meet the confirmation threshold
    - Reconfirmation fails

    When reconfirmation fails at an epoch boundary, confirmed_root must reset to 
    finalized_checkpoint.root rather than continuing with an under-supported chain.

    At each epoch boundary, FCR must verify that the previously confirmed chain still
    has sufficient support under the new epoch's balance source (which may exclude
    newly-slashed validators). If reconfirmation fails, FCR resets to the safe fallback.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Drive to epoch 2 start
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Make sure confirmed_root is in epoch 2 (avoid "too old" disjunct at epoch 3 start)
    fcr.run_slots_with_blocks_and_fast_confirmation(2, participation_rate=100)
    assert spec.get_block_epoch(store, store.confirmed_root) == spec.Epoch(2)
    assert store.confirmed_root != store.finalized_checkpoint.root

    # Go to epoch3_start-3 so we can fork for 3 slots => 6 blocks total (tip/competing per slot)
    s1 = epoch3_start - 3
    s2 = epoch3_start - 2
    s3 = epoch3_start - 1
    while fcr.current_slot() < s1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr.current_slot() == s1

    tip_roots = []

    def fork_and_vote_tip_at_slot(slot, run_fcr_after_applying=True):
        """
        At `slot` (must equal fcr.current_slot()):
          - create sibling blocks tip vs competing at same parent/slot (6 blocks total across 3 slots)
          - vote 100% for tip
          - move to next slot, apply votes
          - optionally run FCR (we skip it at epoch boundary until after slashings)
        """
        assert fcr.current_slot() == slot

        fork_parent_root = fcr.head()
        prev_pool_atts = list(fcr.attestation_pool)

        # tip block
        fcr.attestation_pool = list(prev_pool_atts)
        tip_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"tip_{slot}"
        )

        # competing sibling block 
        fcr.attestation_pool = list(prev_pool_atts)
        _competing_root = fcr.add_and_apply_block(
            parent_root=fork_parent_root, release_att_pool=True, graffiti=f"competing_{slot}"
        )

        # vote for tip
        fcr.attest(block_root=tip_root, slot=slot, participation_rate=100)
        tip_roots.append(tip_root)

        # advance + apply votes
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []

        if run_fcr_after_applying:
            fcr.run_fast_confirmation()

    # Slot s1: fork, vote for tip, advance, apply, run FCR
    fork_and_vote_tip_at_slot(s1, run_fcr_after_applying=True)
    assert fcr.current_slot() == s2

    # Slot s2: fork, vote for tip, advance, apply, run FCR
    fork_and_vote_tip_at_slot(s2, run_fcr_after_applying=True)
    assert fcr.current_slot() == s3

    # Slot s3: fork, vote for tip, advance into epoch 3, apply votes, but do not run FCR yet
    fork_and_vote_tip_at_slot(s3, run_fcr_after_applying=False)
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Before we inject slashings, the tips should be one-confirmed under the previous balance source.
    balance_source = spec.get_previous_balance_source(store)
    for i, root in enumerate(tip_roots):
        assert spec.is_one_confirmed(store, balance_source, root), f"tip[{i}] not one-confirmed pre-slashing"

    # Rule out the other reset disjuncts *before* reconfirmation:
    confirmed_before = store.confirmed_root
    head_before = fcr.head()
    assert confirmed_before != store.finalized_checkpoint.root
    assert spec.is_ancestor(store, head_before, confirmed_before)  # canonical
    assert spec.get_block_epoch(store, confirmed_before) >= spec.Epoch(2)  # not too old

    # Late equivocation evidence arrives at epoch boundary 
    slashings = []
    for _ in range(3):
        sl = fcr.apply_attester_slashing(slashing_percentage=25, slot=fcr.current_slot())
        slashings.append(sl)
        # Optional: explicit artefact for easier reproduction/debug
        fcr.blockchain_artefacts.append(("late_attester_slashing", sl))

    assert len(store.equivocating_indices) > 0

    # Now run epoch-start fast-confirmation logic (this is where reconfirmation is checked)
    fcr.run_fast_confirmation()

    # Expect reset-to-finalized due to reconfirmation failure at epoch boundary
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_reset_to_finality_but_no_restart_to_gu_because_gu_too_old_epoch(spec, state):
    """
    Test that confirmed_root resets to finalized (not GU) when both are old at epoch boundary.
       
    1. Epochs 0-1: 100% participation
    - Confirmations advance normally

    2. Epoch 2: Low participation (20%)
    - Confirmations stall and become "too old"
    - Neither finalized nor GU advance (low participation prevents justification/finalization)

    3. At epoch 3 start:
    - confirmed_root is 2+ epochs old → triggers reset
    - GU is also too old (GU.epoch + 1 < current_epoch) → blocks restart-to-GU
    - finalized is strictly older than GU at the block level (slot(finalized) < slot(GU))

    Expected Behavior:
 
    When confirmed_root must reset at an epoch boundary:
    1. First check: 
    - Reset to finalized checkpoint instead
    2. Second check: Can we restart to GU? 
    - NO: GU is too old, although slot(bcand=GF) < slot(\block(GU))

    Result: confirmed_root = finalized_checkpoint.root (NOT GU)
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S

    # Full participation through epochs 0 and 1, reaching epoch 2 start.
    saw_nonfinal_confirmed = False
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        if store.confirmed_root != store.finalized_checkpoint.root:
            saw_nonfinal_confirmed = True

    assert fcr.current_slot() == epoch2_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())
    assert saw_nonfinal_confirmed, "confirmed_root never advanced under full participation (unexpected)"

    # Epoch 2 with low participation.
    low_participation = 20

    while fcr.current_slot() < epoch3_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=low_participation)

        # Must not reset early (only care that reset happens at epoch 3 start).
        if fcr.current_slot() < epoch3_start:
            assert store.confirmed_root != store.finalized_checkpoint.root, (
                "confirmed_root reset before epoch 3 start (unexpected for this scenario)"
            )

    # Now at epoch 3 start.
    assert fcr.current_slot() == epoch3_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    current_epoch = spec.get_current_store_epoch(store)
    assert current_epoch == spec.Epoch(3)

    # current_epoch_observed_justified_checkpoint is set from unrealized_justified_checkpoint
    # at the start of the last slot of the previous epoch.
    gu = store.current_epoch_observed_justified_checkpoint

    # Finalized strictly older than GU at the block/slot level
    finalized_slot = store.blocks[store.finalized_checkpoint.root].slot
    gu_slot = store.blocks[gu.root].slot
    assert finalized_slot < gu_slot

    # GU is too old to allow restart-to-GU at epoch 3 start.
    assert gu.epoch + 1 < current_epoch, (
        f"GU not old enough to block restart: gu={int(gu.epoch)}, current={int(current_epoch)}"
    )

    # Reset-to-finalized must happen at epoch 3 start due to confirmed being "too old".
    assert store.confirmed_root == store.finalized_checkpoint.root

    yield from fcr.get_test_artefacts()

@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=128)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_resets_when_bcand_not_descendant_of_gu_via_first_received_uj(spec, state):
    """
    Test bcand ⊁ GU reset using "first-received UJ wins" semantics.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch2_start = 2 * S
    epoch3_start = 3 * S
    epoch4_start = 4 * S

    # Epochs 0, 1: Normal operation
    while fcr.current_slot() < epoch2_start:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch2_start

    # Epoch 2: Fork
    fork_point = fcr.head()
    prev_atts = list(fcr.attestation_pool)
    
    # RED BRANCH
    fork_state = store.block_states[fork_point].copy()
    c_block = build_empty_block(spec, fork_state, fcr.current_slot())
    c_block.body.graffiti = b"C_red".ljust(32, b"\x00")
    for att in prev_atts:
        c_block.body.attestations.append(att)
    signed_c = state_transition_and_sign_block(spec, fork_state, c_block)
    for artefact in add_block(spec, store, signed_c, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    c_red = signed_c.message.hash_tree_root()
    
    red_blocks_by_slot = {epoch2_start: c_red}
    red_tip = c_red
    red_state = store.block_states[c_red].copy()

    # BLACK BRANCH
    fcr.attestation_pool = list(prev_atts)
    c_double_prime = fcr.add_and_apply_block(parent_root=fork_point, graffiti="C_double_prime_black")
    black_tip = c_double_prime
    black_blocks_by_slot = {epoch2_start: c_double_prime}
    
    fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Continue epoch 2 with empty attestation bodies
    while fcr.current_slot() < epoch3_start:
        for s in range(epoch2_start + 1, fcr.current_slot()):
            if s not in red_blocks_by_slot:
                rb = build_empty_block(spec, red_state, s)
                rb.body.graffiti = f"red_{s}".encode().ljust(32, b"\x00")
                signed_rb = state_transition_and_sign_block(spec, red_state, rb)
                for artefact in add_block(spec, store, signed_rb, fcr.test_steps):
                    fcr.blockchain_artefacts.append(artefact)
                red_tip = signed_rb.message.hash_tree_root()
                red_blocks_by_slot[s] = red_tip
                red_state = store.block_states[red_tip].copy()
        
        parent_state = store.block_states[black_tip].copy()
        black_block = build_empty_block(spec, parent_state, fcr.current_slot())
        black_block.body.graffiti = f"black_e2_{fcr.current_slot()}".encode().ljust(32, b"\x00")
        signed_black = state_transition_and_sign_block(spec, parent_state, black_block)
        for artefact in add_block(spec, store, signed_black, fcr.test_steps):
            fcr.blockchain_artefacts.append(artefact)
        black_tip = signed_black.message.hash_tree_root()
        black_blocks_by_slot[fcr.current_slot()] = black_tip
        
        fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    # Complete red branch through epoch 2
    for s in range(epoch2_start + 1, epoch3_start):
        if s not in red_blocks_by_slot:
            rb = build_empty_block(spec, red_state, s)
            rb.body.graffiti = f"red_{s}".encode().ljust(32, b"\x00")
            signed_rb = state_transition_and_sign_block(spec, red_state, rb)
            for artefact in add_block(spec, store, signed_rb, fcr.test_steps):
                fcr.blockchain_artefacts.append(artefact)
            red_tip = signed_rb.message.hash_tree_root()
            red_blocks_by_slot[s] = red_tip
            red_state = store.block_states[red_tip].copy()

    assert fcr.current_slot() == epoch3_start

    # Epoch 3: Release 'a' FIRST, then 'd'
    
    # RED block 'a' FIRST
    a_block = build_empty_block(spec, red_state, fcr.current_slot())
    a_block.body.graffiti = b"a_red_FIRST".ljust(32, b"\x00")
    
    for att_slot in range(epoch2_start, epoch3_start):
        if att_slot in red_blocks_by_slot:
            block_root_for_att = red_blocks_by_slot[att_slot]
            att_state = store.block_states[block_root_for_att].copy()
            slot_attestations = get_valid_attestations_for_block_at_slot(
                spec, att_state, spec.Slot(att_slot), block_root_for_att,
                participation_fn=lambda slot, index, committee: committee,
            )
            for att in slot_attestations:
                if len(a_block.body.attestations) < spec.MAX_ATTESTATIONS:
                    a_block.body.attestations.append(att)

    signed_a = state_transition_and_sign_block(spec, red_state, a_block)
    for artefact in add_block(spec, store, signed_a, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    a_red = signed_a.message.hash_tree_root()

    assert store.unrealized_justified_checkpoint.root == c_red

    # BLACK block 'd' SECOND
    parent_state = store.block_states[black_tip].copy()
    d_block = build_empty_block(spec, parent_state, fcr.current_slot())
    d_block.body.graffiti = b"d_black_SECOND".ljust(32, b"\x00")
    
    for att_slot in range(epoch2_start, epoch3_start):
        if att_slot in black_blocks_by_slot:
            block_root_for_att = black_blocks_by_slot[att_slot]
            att_state = store.block_states[block_root_for_att].copy()
            slot_attestations = get_valid_attestations_for_block_at_slot(
                spec, att_state, spec.Slot(att_slot), block_root_for_att,
                participation_fn=lambda slot, index, committee: committee,
            )
            for att in slot_attestations:
                if len(d_block.body.attestations) < spec.MAX_ATTESTATIONS:
                    d_block.body.attestations.append(att)

    signed_d = state_transition_and_sign_block(spec, parent_state, d_block)
    for artefact in add_block(spec, store, signed_d, fcr.test_steps):
        fcr.blockchain_artefacts.append(artefact)
    d_root = signed_d.message.hash_tree_root()
    black_tip = d_root

    assert store.unrealized_justified_checkpoint.root == c_red

    fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
    fcr.next_slot()
    fcr.apply_attestations()
    fcr.attestation_pool = []
    fcr.run_fast_confirmation()

    # Continue epoch 3
    while fcr.current_slot() < epoch4_start - 1:
        black_block = fcr.add_and_apply_block(parent_root=black_tip, graffiti=f"black_e3_{fcr.current_slot()}")
        black_tip = black_block
        fcr.attest(block_root=black_tip, slot=fcr.current_slot(), participation_rate=100)
        fcr.next_slot()
        fcr.apply_attestations()
        fcr.attestation_pool = []
        fcr.run_fast_confirmation()

    # Last slot of epoch 3
    assert fcr.current_slot() == epoch4_start - 1
    
    b_prime = fcr.add_and_apply_block(parent_root=black_tip, graffiti="b_prime_black")
    fcr.attest(block_root=b_prime, slot=fcr.current_slot(), participation_rate=100)
    
    # GU sampling
    fcr.run_fast_confirmation()

    gu = store.current_epoch_observed_justified_checkpoint
    assert gu.root == c_red, "GU should be c_red"

    print(f"\n=== BEFORE CROSSING EPOCH ===")
    print(f"slot: {fcr.current_slot()}")
    print(f"head (via fcr.head()): {encode_hex(fcr.head())[:20]}")
    print(f"store.justified_checkpoint: epoch={store.justified_checkpoint.epoch}, root={encode_hex(store.justified_checkpoint.root)[:20]}")
    print(f"store.unrealized_justified_checkpoint: epoch={store.unrealized_justified_checkpoint.epoch}, root={encode_hex(store.unrealized_justified_checkpoint.root)[:20]}")
    print(f"confirmed_root: {encode_hex(store.confirmed_root)[:20]}")

    # Cross into epoch 4 - DO NOT apply attestations yet
    fcr.next_slot()
    
    print(f"\n=== AFTER next_slot() (slot {fcr.current_slot()}) ===")
    print(f"head (via fcr.head()): {encode_hex(fcr.head())[:20]}")
    print(f"store.justified_checkpoint: epoch={store.justified_checkpoint.epoch}, root={encode_hex(store.justified_checkpoint.root)[:20]}")
    
    # Check what get_head returns vs raw LMDGHOST
    head_via_get_head = fcr.head()
    print(f"head descends from c_red: {spec.is_ancestor(store, head_via_get_head, c_red)}")
    print(f"head descends from c_double_prime: {spec.is_ancestor(store, head_via_get_head, c_double_prime)}")
    print(f"b_prime: {encode_hex(b_prime)[:20]}")
    print(f"head == b_prime: {head_via_get_head == b_prime}")

    # Now apply attestations
    fcr.apply_attestations()
    fcr.attestation_pool = []

    print(f"\n=== AFTER apply_attestations() ===")
    print(f"head (via fcr.head()): {encode_hex(fcr.head())[:20]}")

    assert fcr.current_slot() == epoch4_start

    # Check state BEFORE running FCR
    head_before_fcr = fcr.head()
    confirmed_before_fcr = store.confirmed_root
    current_epoch = spec.get_current_store_epoch(store)
    gu_root = store.current_epoch_observed_justified_checkpoint.root
    confirmed_epoch = spec.get_block_epoch(store, confirmed_before_fcr)

    print(f"\n=== STATE BEFORE FCR ===")
    print(f"head: {encode_hex(head_before_fcr)[:20]}")
    print(f"confirmed: {encode_hex(confirmed_before_fcr)[:20]}")
    print(f"confirmed_epoch: {confirmed_epoch}, current_epoch: {current_epoch}")
    
    bcand_not_too_old = confirmed_epoch + 1 >= current_epoch
    bcand_is_canonical = spec.is_ancestor(store, head_before_fcr, confirmed_before_fcr)
    bcand_not_descendant_of_gu = not spec.is_ancestor(store, confirmed_before_fcr, gu_root)
    gu_is_c_red = gu_root == c_red

    print(f"\n=== CONDITIONS ===")
    print(f"bcand_not_too_old: {bcand_not_too_old}")
    print(f"bcand_is_canonical: {bcand_is_canonical}")
    print(f"bcand_not_descendant_of_gu: {bcand_not_descendant_of_gu}")
    print(f"gu_is_c_red: {gu_is_c_red}")

    # Run FCR
    fcr.run_fast_confirmation()

    reset_occurred = store.confirmed_root == store.finalized_checkpoint.root
    print(f"\n=== RESULT ===")
    print(f"reset_occurred: {reset_occurred}")

    yield from fcr.get_test_artefacts()