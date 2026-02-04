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
def test_fast_confirm_an_epoch(spec, state):
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr.next_slot_with_block_and_fast_confirmation()
        # Ensure head is confirmed
        assert store.confirmed_root == fcr.head()

    yield from fcr.get_test_artefacts()


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

        assert confirmed_slot >= prev_confirmed_slot, \
            f"Confirmed slot went backwards: {prev_confirmed_slot} -> {confirmed_slot}"

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
    2. During mid-epoch slots, observed checkpoints are NOT updated
    3. At the last slot of an epoch, observed checkpoints ARE updated:
       - previous_epoch_observed := current_epoch_observed
       - current_epoch_observed := unrealized_justified_checkpoint
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # 1. Check initial state at genesis
    anchor_root = store.finalized_checkpoint.root
    anchor_epoch = store.finalized_checkpoint.epoch

    assert store.previous_epoch_observed_justified_checkpoint.root == anchor_root
    assert store.previous_epoch_observed_justified_checkpoint.epoch == anchor_epoch
    assert store.current_epoch_observed_justified_checkpoint.root == anchor_root
    assert store.current_epoch_observed_justified_checkpoint.epoch == anchor_epoch

    # Run through epoch 0 to get to epoch 1 
    while fcr.current_slot() < S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == S  # First slot of epoch 1

    # 2. Check mid-epoch slots don't update observed checkpoints 
    # Record values at start of epoch 1
    prev_at_epoch1_start = store.previous_epoch_observed_justified_checkpoint
    curr_at_epoch1_start = store.current_epoch_observed_justified_checkpoint

    # Run through mid-epoch slots (slots 1 to S-2 within epoch 1)
    last_slot_of_epoch1 = 2 * S - 1
    while fcr.current_slot() < last_slot_of_epoch1 - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        # Should NOT be a GU sampling slot
        assert not spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), \
            f"Slot {fcr.current_slot()} should not trigger GU sampling"

        # Observed checkpoints should NOT have changed
        assert store.previous_epoch_observed_justified_checkpoint == prev_at_epoch1_start, \
            f"previous_epoch_observed changed at mid-epoch slot {fcr.current_slot()}"
        assert store.current_epoch_observed_justified_checkpoint == curr_at_epoch1_start, \
            f"current_epoch_observed changed at mid-epoch slot {fcr.current_slot()}"

    # 3. Check last slot of epoch DOES update observed checkpoints
    assert fcr.current_slot() == last_slot_of_epoch1 - 1

    # Record state before the critical slot
    curr_before_last_slot = store.current_epoch_observed_justified_checkpoint

    # Advance to last slot of epoch 1 and run FCR
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == last_slot_of_epoch1
    assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1)), \
        f"Slot {fcr.current_slot()} should trigger GU sampling (next slot is epoch start)"

    # After update_fast_confirmation_variables runs:
    # - previous_epoch_observed should now equal what current_epoch_observed was
    # - current_epoch_observed should now equal unrealized_justified_checkpoint
    assert store.previous_epoch_observed_justified_checkpoint == curr_before_last_slot, \
        "previous_epoch_observed should have been set to old current_epoch_observed"
    assert store.current_epoch_observed_justified_checkpoint == store.unrealized_justified_checkpoint, \
        "current_epoch_observed should equal unrealized_justified_checkpoint after sampling"

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
    Test properties of observed justified checkpoints across multiple epochs:
    
    1. At each epoch boundary, previous := current, current := unrealized
    2. Observed checkpoint epochs never decrease under full participation
    3. current_observed equals unrealized at sampling moment (last slot of epoch)
    4. previous_observed is always one epoch behind current_observed
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    prev_current_observed_epoch = store.current_epoch_observed_justified_checkpoint.epoch
    prev_previous_observed_epoch = store.previous_epoch_observed_justified_checkpoint.epoch
    
    observed_history = []

    for epoch in range(4):  # Run through epochs 0, 1, 2, 3
        last_slot = (epoch + 1) * S - 1

        # Run to last slot of this epoch
        while fcr.current_slot() < last_slot:
            fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

            # Observed checkpoint epochs never decrease under full participation -- check at every slot 
            current_observed_epoch = store.current_epoch_observed_justified_checkpoint.epoch
            previous_observed_epoch = store.previous_epoch_observed_justified_checkpoint.epoch

            assert current_observed_epoch >= prev_current_observed_epoch, \
                f"current_epoch_observed went backwards: {prev_current_observed_epoch} -> {current_observed_epoch}"
            assert previous_observed_epoch >= prev_previous_observed_epoch, \
                f"previous_epoch_observed went backwards: {prev_previous_observed_epoch} -> {previous_observed_epoch}"

            prev_current_observed_epoch = current_observed_epoch
            prev_previous_observed_epoch = previous_observed_epoch

        # Now at last slot of epoch
        assert fcr.current_slot() == last_slot
        assert spec.is_start_slot_at_epoch(spec.Slot(fcr.current_slot() + 1))

        # === Current_observed equals unrealized at sampling moment
        assert store.current_epoch_observed_justified_checkpoint == store.unrealized_justified_checkpoint, \
            f"At epoch {epoch} last slot: current_observed != unrealized"

        # Record for cascade check
        observed_history.append({
            'epoch': epoch,
            'previous_observed_epoch': int(store.previous_epoch_observed_justified_checkpoint.epoch),
            'current_observed_epoch': int(store.current_epoch_observed_justified_checkpoint.epoch),
            'current_observed': store.current_epoch_observed_justified_checkpoint,
        })

    # At epoch E's last slot, previous_observed should equal what current_observed was at epoch E-1's last slot
    for i in range(1, len(observed_history)):
        prev_record = observed_history[i - 1]
        curr_record = observed_history[i]

        assert curr_record['previous_observed_epoch'] == prev_record['current_observed_epoch'], \
            f"Cascade broken at epoch {curr_record['epoch']}: " \
            f"previous_observed={curr_record['previous_observed_epoch']} " \
            f"but prior current_observed was {prev_record['current_observed_epoch']}"

    # previous_observed at epoch 2 end should equal current_observed at epoch 1 end
    assert store.previous_epoch_observed_justified_checkpoint == observed_history[2]['current_observed'], \
        "previous_observed at epoch 3 end should equal current_observed at epoch 2 end"

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