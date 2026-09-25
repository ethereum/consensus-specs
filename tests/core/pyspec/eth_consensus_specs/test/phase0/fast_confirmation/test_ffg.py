from eth_consensus_specs.test.context import (
    default_activation_threshold,
    default_balances,
    MINIMAL,
    never_bls,
    only_generator,
    single_phase,
    spec_test,
    with_altair_and_later,
    with_custom_state,
    with_electra_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.deposits import (
    prepare_deposit_request,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    Attesting,
    FCRTest,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    is_ancestor,
)

"""
Test will_no_conflicting_checkpoint_be_justified
"""


@only_generator("too slow")
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=96)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
@never_bls
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
        spec.get_head(store).root
    ].epoch + 1 >= spec.get_current_store_epoch(store)
    assert is_ancestor(spec, store, fcr_store.previous_slot_head, target_root)

    # Check will_no_conflicting_checkpoint_be_justified fails
    assert not spec.will_no_conflicting_checkpoint_be_justified(store)

    # Run Fast confirmation
    fcr.run_fast_confirmation()

    assert fcr_store.confirmed_root == confirmed_epoch_2_last_slot

    yield from fcr.get_test_artefacts()


@only_generator("too slow")
@with_electra_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=default_balances,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
@never_bls
def test_will_no_conflicting_checkpoint_be_justified_fails_with_new_validator_activated_in_head_state(
    spec, state
):
    """
    1. Deposit a new large validator that could affect the FFG check.
    2. Move to the activationn epoch, validator is not yet active in the balance source,
       but already active in the head state. Leave a target block in the epoch prior to activation unconfirmed.
    3. Move to a mid epoch slot with 0 participation to delay confirmation;
       then attest to the checkpoint block by a new validator committee but except for a new validator;
       also attest to the target block by all previous committees.
    4. Check that is_one_confirmed passes, but the FFG check fails because the latter
       is computed over the head state.
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    # Move to Epoch 2 Slot 1
    while fcr.current_slot() < 2 * spec.SLOTS_PER_EPOCH + 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Create a block with a large validator deposit
    new_val_index = len(state.validators)
    new_val_balance = 8 * spec.MIN_ACTIVATION_BALANCE
    withdrawal_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    deposit = prepare_deposit_request(
        spec,
        new_val_index,
        new_val_balance,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )
    fcr.add_and_apply_block(deposit_requests=[deposit])
    fcr.attest()
    fcr.next_slot()
    fcr.run_fast_confirmation()

    # Wait for a new validator to get onboarded
    while fcr.current_slot() < 10 * spec.SLOTS_PER_EPOCH:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert len(store.block_states[fcr.head_root()].validators) > new_val_index

    # Run to the last slot of the BEFORE activation epoch with full participation
    while True:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
        activation_epoch = (
            store.block_states[fcr.head_root()].validators[new_val_index].activation_epoch
        )
        if (
            activation_epoch != spec.FAR_FUTURE_EPOCH
            and fcr.current_slot() + 1 == spec.compute_start_slot_at_epoch(activation_epoch)
        ):
            break

    # Create a block with support enough for reconfirmation to pass but still delay a confirmation
    # of that block
    b_root = fcr.next_slot_with_block_and_fast_confirmation(
        participation_rate=75, graffiti="target"
    )

    # Create a checkpoint block
    checkpoint_root = fcr.next_slot_with_block_and_fast_confirmation(
        participation_rate=0, graffiti="checkpoint"
    )

    # Run to the middle of an epoch with 0 participation
    for _ in range(4):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=0)

    start_slot_at_epoch = spec.compute_start_slot_at_epoch(fcr.current_epoch())
    attested_to_checkpoint_cnt = 0
    for slot in range(start_slot_at_epoch, fcr.current_slot()):
        attesters = spec.get_slot_committee(store, spec.Slot(slot))
        # Attest to checkpoint block by at least 2 committees including the one with
        # a new validator
        if attested_to_checkpoint_cnt < 2 or new_val_index in attesters:
            attesters.discard(new_val_index)
            fcr.attest(block_root=checkpoint_root, attester_indices=attesters, slot=slot)
            attested_to_checkpoint_cnt += 1
        else:
            # Attest to target block
            fcr.attest(block_root=b_root, slot=slot)

    # Advance slot
    fcr.next_slot()

    # Check precondition
    balance_source = spec.get_current_balance_source(fcr_store)
    head_state = spec.get_pulled_up_head_state(store)
    # New validator is not yet active in the balance source
    assert not spec.is_active_validator(
        balance_source.validators[new_val_index], spec.get_current_epoch(balance_source)
    )
    # But it is already active in the head state
    assert spec.is_active_validator(
        head_state.validators[new_val_index], spec.get_current_epoch(head_state)
    )
    # Ensure that is_one_confirmed passes
    assert spec.is_one_confirmed(store, balance_source, b_root)
    # But will_no_conflicting_checkpoint_be_justified fails
    assert not spec.will_no_conflicting_checkpoint_be_justified(store)

    # The block must not be confirmed
    previosly_confirmed_root = fcr_store.confirmed_root
    fcr.run_fast_confirmation()
    assert fcr_store.confirmed_root == previosly_confirmed_root

    yield from fcr.get_test_artefacts()


"""
Test will_current_target_be_justified
"""


@only_generator("too slow")
@with_altair_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=(lambda spec: default_balances(spec, num_validators=96)),
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
@never_bls
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


@only_generator("too slow")
@with_electra_and_later
@with_presets([MINIMAL], reason="too slow")
@with_custom_state(
    balances_fn=default_balances,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
@never_bls
def test_will_current_target_be_justified_fails_with_new_validator_activated_in_head_state(
    spec, state
):
    """
    1. Deposit a new large validator that could affect the FFG check.
    2. Move to the activationn epoch, validator is not yet active in the balance source,
       but already active in the head state.
    3. Move to a slot where a new validator would attest with 0 participation to delay confirmation;
       then attest with the whole committee except for a new validator;
       also attest to all previous blocks.
    4. Check that is_one_confirmed passes, but the FFG check fails because the latter
       is computed over the head state.
    """
    fcr = FCRTest(spec, seed=1)
    store, fcr_store = fcr.initialize(state)

    # Move to Epoch 2 Slot 1
    while fcr.current_slot() < 2 * spec.SLOTS_PER_EPOCH + 1:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Create a block with a large validator deposit
    new_val_index = len(state.validators)
    new_val_balance = 8 * spec.MIN_ACTIVATION_BALANCE
    withdrawal_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    deposit = prepare_deposit_request(
        spec,
        new_val_index,
        new_val_balance,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )
    fcr.add_and_apply_block(deposit_requests=[deposit])
    fcr.attest()
    fcr.next_slot()
    fcr.run_fast_confirmation()

    # Wait for a new validator to get onboarded
    while fcr.current_slot() < 10 * spec.SLOTS_PER_EPOCH:
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert len(store.block_states[fcr.head_root()].validators) > new_val_index

    # Run to the activation epoch
    while (
        fcr.current_epoch()
        < store.block_states[fcr.head_root()].validators[new_val_index].activation_epoch
    ):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=100)

    # Run to a slot where a new validator is attesting with 0 participation
    while new_val_index not in spec.get_slot_committee(store, fcr.current_slot()):
        fcr.next_slot_with_block_and_fast_confirmation(participation_rate=0)

    # Propose and attest with all validators except for the new_val_index
    attesters = spec.get_slot_committee(store, fcr.current_slot())
    attesters.discard(new_val_index)
    b_root = fcr.add_and_apply_block(graffiti="target")
    fcr.attest(attester_indices=attesters)

    # Attest to all previous blocks
    start_slot_at_epoch = spec.compute_start_slot_at_epoch(fcr.current_epoch())
    for slot in range(start_slot_at_epoch, fcr.current_slot()):
        Attesting(block_id=slot, committee_slot_or_offset=slot).execute(fcr)

    # Advance slot
    fcr.next_slot()

    # Check precondition
    balance_source = spec.get_current_balance_source(fcr_store)
    head_state = spec.get_pulled_up_head_state(store)
    # New validator is not yet active in the balance source
    assert not spec.is_active_validator(
        balance_source.validators[new_val_index], spec.get_current_epoch(balance_source)
    )
    # But it is already active in the head state
    assert spec.is_active_validator(
        head_state.validators[new_val_index], spec.get_current_epoch(head_state)
    )
    # Ensure that is_one_confirmed passes
    assert spec.is_one_confirmed(store, balance_source, b_root)
    # But will_current_target_be_justified fails
    assert not spec.will_current_target_be_justified(store)

    # The block must not be confirmed
    previosly_confirmed_root = fcr_store.confirmed_root
    fcr.run_fast_confirmation()
    assert fcr_store.confirmed_root == previosly_confirmed_root

    yield from fcr.get_test_artefacts()
