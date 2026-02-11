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
    SystemRun,
)

"""
Test on restart to GU
"""


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_restarts_to_gu_when_all_conditions_met(spec, state):
    """
    Test that confirmed_root restarts to GU (not finalized) when all conditions are met:
    1. At epoch start
    2. GU.epoch + 1 == current_epoch (GU is fresh)
    3. GU == unrealized_justifications[head]
    4. slot(confirmed) < slot(block(GU))

    Strategy:
    - Epochs 0-4: 100% participation, confirmations and justification advance
    - Last slot of epoch 4: GU sampling happens, then late slashing arrives
    - Epoch 5 start: reconfirmation fails due to slashed weight
      * GU (epoch 4) is fresh, slot(finalized) < slot(GU)
      * → restart to GU instead of staying at finalized
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch5_start = 5 * S

    # Epochs 0-4: Full participation (up to last slot of epoch 4)
    while fcr.current_slot() < epoch5_start - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    assert fcr.current_slot() == epoch5_start - 1
    assert store.finalized_checkpoint.epoch >= spec.Epoch(2)

    # Last slot of epoch 4: build block, attest
    block_root = fcr.add_and_apply_block(parent_root=fcr.head())
    lslot_atts = fcr.attest(block_root=block_root, slot=fcr.current_slot(), participation_rate=100)

    # Late slashing arrives during last slot of epoch 4 (before crossing into epoch 5)
    fcr.apply_attester_slashing(slashing_percentage=50, slot=fcr.current_slot())

    # Cross into epoch 5 atomically: tick + apply attestations
    fcr.next_slot()
    fcr.apply_attestations(lslot_atts)

    assert fcr.current_slot() == epoch5_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Verify preconditions for restart-to-GU
    confirmed_before = store.confirmed_root
    gu = store.current_epoch_observed_justified_checkpoint
    finalized = store.finalized_checkpoint.root
    head = fcr.head()
    head_uj = store.unrealized_justifications[head]
    current_epoch = spec.get_current_store_epoch(store)

    gu_slot = spec.get_block_slot(store, gu.root)
    finalized_slot = spec.get_block_slot(store, finalized)

    assert gu.epoch + 1 == current_epoch, f"GU not fresh: {gu.epoch} + 1 != {current_epoch}"
    assert confirmed_before != finalized, "Should have confirmations before FCR"
    assert gu == head_uj, "GU != head's UJ"
    assert finalized_slot < gu_slot, f"slot(finalized)={finalized_slot} >= slot(GU)={gu_slot}"
    assert gu.root != finalized, "GU == finalized (test not meaningful)"

    # Run FCR - should reset due to reconfirmation failure, then restart to GU
    fcr.run_fast_confirmation()

    # Verify restart to GU (not finalized)
    assert store.confirmed_root == gu.root, "Should restart to GU"
    assert store.confirmed_root != finalized, "Should NOT stay at finalized"

    yield from fcr.get_test_artefacts()


# test_reset_to_finality_but_no_restart_to_gu_because_gu_too_old_epoch can be considered
# also for this test case scenario. See test_revert_finality.py


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_restarts_to_gu_and_confirms_beyond_gu(spec, state):
    """
    Test that confirmed_root restarts to GU (not finalized)
    and confirms a more recent block than gu.root

    Strategy:
    - Epochs 0-4: 100% participation, confirmations and justification advance
    - Last slot of epoch 4: GU sampling happens, then late slashing arrives
    - Epoch 5 start: reconfirmation fails due to slashed weight
      * GU (epoch 4) is fresh, slot(finalized) < slot(GU)
      * → restart to GU instead of staying at finalized and advance further via
          find_latest_confirmed_descendant
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH
    epoch5_start = 5 * S

    # Epochs 0-4: Full participation (up to last slot of epoch 4)
    while fcr.current_slot() < epoch5_start - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

        if fcr.current_slot() == epoch5_start - 2:
            expected_confirmed_root_after_restart = store.confirmed_root

    assert fcr.current_slot() == epoch5_start - 1
    assert store.finalized_checkpoint.epoch >= spec.Epoch(2)

    # Last slot of epoch 4: build block, attest
    block_root = fcr.add_and_apply_block(parent_root=fcr.head())
    lslot_atts = fcr.attest(block_root=block_root, slot=fcr.current_slot(), participation_rate=100)

    # Late slashing arrives during last slot of epoch 4 (before crossing into epoch 5)
    # Slash the whole committee of the last slot of epoch 4, this will make reconfirmation
    # for penultimate block slot fail and after restart advance confirmation to block in a slot before the penultimate one
    fcr.execute_run(
        SystemRun(
            number_of_slots=0, slashing_percentage=100, slash_participants_in_slot_with_offset=0
        )
    )

    # Cross into epoch 5 atomically: tick + apply attestations
    fcr.next_slot()
    fcr.apply_attestations(lslot_atts)

    assert fcr.current_slot() == epoch5_start
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Verify preconditions for restart-to-GU
    confirmed_before = store.confirmed_root
    gu = store.current_epoch_observed_justified_checkpoint
    finalized = store.finalized_checkpoint.root
    head = fcr.head()
    head_uj = store.unrealized_justifications[head]
    current_epoch = spec.get_current_store_epoch(store)

    gu_slot = spec.get_block_slot(store, gu.root)
    finalized_slot = spec.get_block_slot(store, finalized)

    assert gu.epoch + 1 == current_epoch, f"GU not fresh: {gu.epoch} + 1 != {current_epoch}"
    assert confirmed_before != finalized, "Should have confirmations before FCR"
    assert gu == head_uj, "GU != head's UJ"
    assert finalized_slot < gu_slot, f"slot(finalized)={finalized_slot} >= slot(GU)={gu_slot}"
    assert gu.root != finalized, "GU == finalized (test not meaningful)"

    # Run FCR - should reset due to reconfirmation failure, then restart to GU
    fcr.run_fast_confirmation()

    # Verify restart to GU (not finalized)
    assert store.confirmed_root == expected_confirmed_root_after_restart, (
        "Should restart to GU and advance further"
    )
    assert store.confirmed_root != finalized, "Should NOT stay at finalized"

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_no_restart_to_gu_mid_epoch(spec, state):
    """
    Test that restart-to-GU only triggers at epoch boundaries, not mid-epoch.

    Scenario:
    1. Epochs 0-2: 100% participation, confirmations advance
    2. Mid-epoch 3: Drop to 20% participation
       - Confirmation stops advancing
    3. Continue through epoch 3 and 4 with 20%
       - Verify: confirmed never jumps backward to GU mid-epoch
       - It either stays the same or advances monotonically
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Epochs 0-2: Full participation
    while fcr.current_slot() < 3 * S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    confirmed_after_epoch2 = store.confirmed_root
    assert spec.get_block_epoch(store, confirmed_after_epoch2) == spec.Epoch(2)

    # Early epoch 3: Continue 100% for a few slots
    epoch3_mid = 3 * S + S // 2

    while fcr.current_slot() < epoch3_mid:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    confirmed_mid_epoch3 = store.confirmed_root
    assert spec.get_block_epoch(store, confirmed_mid_epoch3) == spec.Epoch(3)

    # Rest of epoch 3 + all of epoch 4: Drop to 20%
    # Track confirmed at each slot to verify no mid-epoch restart
    prev_confirmed = store.confirmed_root

    while fcr.current_slot() < 5 * S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=20)

        current_confirmed = store.confirmed_root

        # Confirmed should be monotonic (same or descendant), never jump backward
        assert current_confirmed == prev_confirmed or spec.is_ancestor(
            store, prev_confirmed, current_confirmed
        ), "Confirmed should be monotonic mid-epoch, not restart to GU"

        prev_confirmed = current_confirmed

    yield from fcr.get_test_artefacts()


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_fcr_no_restart_to_gu_because_gu_too_old(spec, state):
    """
    Test that restart-to-GU fails when GU.epoch < current_epoch - 1.

    Scenario:
    1. Epochs 0-2: 100% participation, confirmations advance
    2. Mid-epoch 3: Drop to 20% participation
       - Confirmation stops advancing
       - Justification stops (can't reach 2/3)
    3. Continue 20% through epoch 4
    4. Epoch 4->5 boundary:
       - b_cand is too old (epoch 3) -> reset to finalized
       - GU is stale (epoch 2) -> restart-to-GU condition fails
       - Verify: confirmed == finalized, NOT GU
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Epochs 0-2: Full participation
    while fcr.current_slot() < 3 * S:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    confirmed_after_epoch2 = store.confirmed_root
    assert spec.get_block_epoch(store, confirmed_after_epoch2) == spec.Epoch(2)

    # Early epoch 3: Continue 100% for a few slots
    epoch3_mid = 3 * S + S // 2

    while fcr.current_slot() < epoch3_mid:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    confirmed_mid_epoch3 = store.confirmed_root
    assert spec.get_block_epoch(store, confirmed_mid_epoch3) == spec.Epoch(3)

    # Rest of epoch 3 + all of epoch 4: Drop to 20%
    while fcr.current_slot() < 5 * S - 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=20)

    # Last slot of epoch 4, Epoch 4->5 boundary
    fcr.next_slot_with_block_and_apply_attestations(participation_rate=20)

    assert fcr.current_slot() == 5 * S
    assert spec.is_start_slot_at_epoch(fcr.current_slot())

    # Capture state before FCR
    confirmed_before = store.confirmed_root
    confirmed_epoch_before = spec.get_block_epoch(store, confirmed_before)
    gu = store.current_epoch_observed_justified_checkpoint
    finalized = store.finalized_checkpoint
    current_epoch = spec.get_current_store_epoch(store)

    # Verify preconditions:
    # 1. b_cand is too old (should trigger reset)
    assert confirmed_epoch_before < current_epoch - 1, (
        f"b_cand epoch {confirmed_epoch_before} should be < {current_epoch - 1}"
    )

    # 2. GU is stale (restart-to-GU should fail)
    assert gu.epoch < current_epoch - 1, (
        f"GU epoch {gu.epoch} should be < {current_epoch - 1} (stale)"
    )

    # Run FCR
    fcr.run_fast_confirmation()

    confirmed_after = store.confirmed_root

    # Should have reset to finalized
    assert confirmed_after == finalized.root, (
        f"Should reset to finalized, not stay at {confirmed_before}"
    )

    # Should NOT have restarted to GU (because GU is too old)
    assert confirmed_after != gu.root or gu.root == finalized.root, (
        "Should not restart to GU when GU is stale"
    )

    yield from fcr.get_test_artefacts()
