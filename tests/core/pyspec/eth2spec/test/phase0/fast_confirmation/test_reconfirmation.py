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
Test is_confirmed_chain_safe
"""


@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_reconfirmation_passes_wtih_empty_slots_prior_first_block(spec, state):
    """
    1. Build until last slot of epoch 2 with 100% participation
    2. Leave last slot of epoch 2 empty
    3. Leave first slot of epoch 3 empty
    4. Slash 25% of validators in these two slots
    5. Run until the start of epoch 3 with blocks and 100% participation.
       Confirm the first block in epoch 3.
    6. Check that reconfirmation did not fail
       In this case reconfirmation will involve committees and equivocated validators
       from current_epoch - 2.
    """
    fcr = FCRTest(spec, seed=1)
    store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Run until last slot of epoch 2
    fcr.run_slots_with_blocks_and_fast_confirmation(3 * S - 1, participation_rate=100)

    confimed_at_last_slot_epoch_2 = store.confirmed_root

    # Leave last slot empty
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=100)

    # Check that reconfirmation passed
    assert store.confirmed_root == confimed_at_last_slot_epoch_2

    # Epoch 3, Slot 1, empty slot
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=100)

    # Epoch 3, Slot 2, with block
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Check that confirmed block was not advanced
    assert store.confirmed_root == confimed_at_last_slot_epoch_2

    # Epoch 3, Slot 3

    # Slash participants of (Epoch 2, last slot) and (Epoch 3, first slot)
    fcr.execute_run(
        SystemRun(
            number_of_slots=0,
            slashing_percentage=25,
            slash_participants_in_slot_with_offset=-4,
        )
    )
    fcr.execute_run(
        SystemRun(
            number_of_slots=0,
            slashing_percentage=25,
            slash_participants_in_slot_with_offset=-3,
        )
    )

    # Advance with block
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Check confirmed block was not advanced
    assert store.confirmed_root == confimed_at_last_slot_epoch_2

    # Epoch 3, Slot 4 with block
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Check the head is confirmed
    assert store.confirmed_root == fcr.head()

    # But if there were no slashings, first block in Epoch 3 couldn't be confirmed at this stage
    epoch_3_first_block = spec.get_ancestor(store, fcr.head(), 3 * S + 1)
    balance_source = spec.get_current_balance_source(store)

    support = spec.get_attestation_score(store, epoch_3_first_block, balance_source)
    proposer_score = spec.compute_proposer_score(balance_source)
    maximum_support = spec.estimate_committee_weight_between_slots(
        spec.get_total_active_balance(balance_source),
        spec.Slot(3 * S - 1),
        spec.Slot(fcr.current_slot() - 1),
    )

    # Subtract the slashed balance from the discount
    # 25% of 2 slots * (len(validators) // SLOTS_PER_EPOCH * effective_balance)
    slashed_balance = 2 * (len(state.validators) // S * state.validators[0].effective_balance // 4)
    support_discount = (
        spec.get_support_discount(store, balance_source, epoch_3_first_block) - slashed_balance
    )

    adversarial_weight = spec.get_adversarial_weight(store, balance_source, epoch_3_first_block)

    # Check the support is lower than the support threshold
    assert (
        2 * support + support_discount < maximum_support + proposer_score + 2 * adversarial_weight
    )

    # Run till last slot of Epoch 3
    fcr.execute_run(SystemRun(end_slot=(4 * S - 1), participation_rate=100))

    # Check the head was confirmed
    assert store.confirmed_root == fcr.head()

    # Run to the start of Epoch 4 with no block
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=100)

    # Check reconfirmation passed
    assert store.confirmed_root == fcr.head()

    yield from fcr.get_test_artefacts()
