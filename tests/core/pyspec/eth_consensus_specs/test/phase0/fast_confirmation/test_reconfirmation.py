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
    Attesting,
    FCRTest,
    Slashing,
    SlotSequence,
)

"""
Test is_confirmed_chain_safe
"""


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=64)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_reconfirmation_passes_with_empty_slots_prior_first_block(spec, state):
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
    store, fcr_store = fcr.initialize(state)

    S = spec.SLOTS_PER_EPOCH

    # Run until last slot of epoch 2
    fcr.run_slots_with_blocks_and_fast_confirmation(3 * S - 1, participation_rate=100)

    confirmed_at_last_slot_epoch_2 = fcr_store.confirmed_root

    # Leave last slot empty
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=100)

    # Check that reconfirmation passed
    assert fcr_store.confirmed_root == confirmed_at_last_slot_epoch_2

    # Epoch 3, Slot 1, empty slot
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=100)

    # Epoch 3, Slot 2, with block
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Check that confirmed block was not advanced
    assert fcr_store.confirmed_root == confirmed_at_last_slot_epoch_2

    # Epoch 3, Slot 3

    # Slash participants of (Epoch 2, last slot) and (Epoch 3, first slot)
    Slashing(percentage=25, committee_slot_or_offset=3 * S - 1).execute(fcr)
    Slashing(percentage=25, committee_slot_or_offset=3 * S).execute(fcr)

    # Advance with block and attest to add a bit more weight to overcome the committee shuffling dispersion
    fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=75)

    # Check the head is confirmed
    assert fcr_store.confirmed_root == fcr.head()

    # But if there were no slashings, first block in Epoch 3 couldn't be confirmed at this stage
    epoch_3_first_block = spec.get_ancestor(store, fcr.head(), 3 * S + 1)
    balance_source = spec.get_current_balance_source(fcr_store)
    support = spec.get_attestation_score(store, epoch_3_first_block, balance_source)
    safety_threshold = spec.compute_safety_threshold(store, epoch_3_first_block, balance_source)

    # Compute slashed balance
    # 25% of 2 slots * (len(validators) // SLOTS_PER_EPOCH * effective_balance)
    slashed_balance = 2 * (len(state.validators) // S * state.validators[0].effective_balance // 4)

    # Add a half of slashed balance back to the safety threshold
    # and check the support would be lower than the threshold
    assert support < safety_threshold + slashed_balance // 2

    # Run till last slot of Epoch 3
    SlotSequence(end_slot=(4 * S - 1), attesting=Attesting(participation_rate=100)).execute(fcr)

    # Check the head was confirmed
    assert fcr_store.confirmed_root == fcr.head()

    # Run to the start of Epoch 4 with no block
    fcr.attest_and_next_slot_with_fast_confirmation(participation_rate=100)

    # Check reconfirmation passed
    assert fcr_store.confirmed_root == fcr.head()

    yield from fcr.get_test_artefacts()
