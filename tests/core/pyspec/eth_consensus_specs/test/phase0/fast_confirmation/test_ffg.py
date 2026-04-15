from eth_consensus_specs.test.context import (
    default_activation_threshold,
    default_balances,
    MINIMAL,
    single_phase,
    spec_test,
    with_all_phases_from_to,
    with_custom_state,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    ALTAIR,
    FULU,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    Attesting,
    FCRTest,
)

"""
Test will_no_conflicting_checkpoint_be_justified
"""


@with_all_phases_from_to(ALTAIR, FULU)
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=96)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_will_no_conflicting_checkpoint_be_justified_fails_at_strictly_one_third(spec, state):
    """
    Based on the fact that there are 96 vals in total.
    1. Run to Epoch 2, Last Slot and create "target" block.
    2. Run to Epoch 3, Slot 0 with successful reconfirmation.
    3. Run several slots and manipulate with votes to make
       honest_ffg_support_for_current_target == total_active balance // 3
    4. Check the one_confirmed passes for a block but will_no_conflicting_checkpoint_be_justified fails
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Up to target slot
    target_slot = 2 * S - 1
    fcr.run_slots_with_blocks_and_fast_confirmation(target_slot, participation_rate=100)

    confirmed_epoch_2_last_slot = fcr_store.confirmed_root

    # Epoch 2, Last Slot with participation enough pass reconfirmation, but still not enoug to confirm
    target_root = fcr.next_slot_with_block_and_fast_confirmation(
        participation_rate=92, graffiti="target"
    )

    # Epoch 3, Slot 0 with no attestations to prevent "target" from confirming
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=0, graffiti="chkp")

    # To Epoch 3, Slot 4
    for _ in range(3):
        fcr.next_slot()
        fcr.run_fast_confirmation()

    fcr.print_fast_confirmation_state()

    # Attest with a strict rate to ensure honest_ffg_support_for_current_target == total_active_balance // 3
    Attesting(
        participation_rate=25, block_id="chkp", committee_slot_or_offset=[-1, -2, -3]
    ).execute(fcr)
    Attesting(participation_rate=92, block_id="chkp", committee_slot_or_offset=0).execute(fcr)

    # Attest to "target" to make is_one_confirmed pass
    Attesting(
        participation_rate=100, block_id="target", committee_slot_or_offset=[0, -1, -2, -3]
    ).execute(fcr)

    # To Epoch 3, Slot 5
    fcr.next_slot()

    fcr.print_fast_confirmation_state()

    # Check the honest_ffg_support_for_current_target
    balance_source = spec.get_pulled_up_head_state(store)
    honest_ffg_support_for_current_target = spec.compute_honest_ffg_support_for_current_target(
        store
    )
    assert 3 * honest_ffg_support_for_current_target == spec.get_total_active_balance(
        balance_source
    )

    # Check all other conditions passes, so a block would be confirmed
    assert spec.is_one_confirmed(store, spec.get_current_balance_source(fcr_store), target_root)
    assert spec.get_voting_source(
        store, fcr_store.previous_slot_head
    ).epoch + 2 >= spec.get_current_store_epoch(store)
    assert store.unrealized_justifications[
        spec.get_head(store)
    ].epoch + 1 >= spec.get_current_store_epoch(store)
    assert spec.is_ancestor(store, fcr_store.previous_slot_head, target_root)

    # Check will_no_conflicting_checkpoint_be_justified fails
    assert not spec.will_no_conflicting_checkpoint_be_justified(store)

    # Run Fast confirmation
    fcr.run_fast_confirmation()

    assert fcr_store.confirmed_root == confirmed_epoch_2_last_slot

    yield from fcr.get_test_artefacts()


"""
Test will_current_target_be_justified
"""


@with_all_phases_from_to(ALTAIR, FULU)
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=96)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_will_current_target_be_justified_passes_at_strictly_two_third(spec, state):
    """
    Based on the fact that there are 96 vals in total.
    1. Run to Epoch 2, Slot 0 with full participation
    2. Do not confirm Epoch 2 chkp block
    3. Manipulate with slots and attestation to make that block one confirmed and
       3 * honest_ffg_support_for_current_target == 2 * total_active_balance
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # To Epoch 2, Slot 0 with full participation
    fcr.run_slots_with_blocks_and_fast_confirmation(S - 1, participation_rate=100)
    confirmed_epoch_1_last_slot = fcr.next_slot_with_block_and_fast_confirmation(
        participation_rate=100
    )

    # Epoch 2 checkpoint block, prevent one confirm
    chkp_root = fcr.next_slot_with_block_and_fast_confirmation(participation_rate=92)

    # To Epoch 2, Slot 2 with low participation to avoid passing of will_current_target_be_justified
    for _ in range(2):
        fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=75)

    # To Epoch 2, Slot 3 with participation enough for one confirm and will_current_target_be_justified to pass
    fcr.attest(participation_rate=92)
    fcr.next_slot()

    # Check the honest_ffg_support_for_current_target
    balance_source = spec.get_pulled_up_head_state(store)
    honest_ffg_support_for_current_target = spec.compute_honest_ffg_support_for_current_target(
        store
    )
    assert 3 * honest_ffg_support_for_current_target == 2 * spec.get_total_active_balance(
        balance_source
    )

    # Check will_current_target_be_justified passes
    assert spec.will_current_target_be_justified(store)

    assert fcr_store.confirmed_root == confirmed_epoch_1_last_slot

    # Run Fast confirmation
    fcr.run_fast_confirmation()

    assert fcr_store.confirmed_root == chkp_root

    yield from fcr.get_test_artefacts()
