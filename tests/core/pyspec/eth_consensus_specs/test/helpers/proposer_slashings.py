import pytest

from eth_consensus_specs.test.helpers.block_header import sign_block_header
from eth_consensus_specs.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_electra,
    is_post_gloas,
)
from eth_consensus_specs.test.helpers.keys import pubkey_to_privkey
from eth_consensus_specs.test.helpers.state import get_balance, next_epoch
from eth_consensus_specs.test.helpers.sync_committee import (
    compute_committee_indices,
    compute_sync_committee_participant_reward_and_penalty,
)


def get_min_slashing_penalty_quotient(spec):
    if is_post_electra(spec):
        return spec.MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA
    elif is_post_bellatrix(spec):
        return spec.MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX
    elif is_post_altair(spec):
        return spec.MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR
    else:
        return spec.MIN_SLASHING_PENALTY_QUOTIENT


def get_whistleblower_reward_quotient(spec):
    if is_post_electra(spec):
        return spec.WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA
    else:
        return spec.WHISTLEBLOWER_REWARD_QUOTIENT


def check_proposer_slashing_effect(
    spec, pre_state, state, slashed_index, block=None, proposer_slashing=None
):
    """
    Verify all state changes from a successful proposer slashing.

    Args:
        spec: The spec module for the fork being tested
        pre_state: State before slashing was processed
        state: State after slashing was processed
        slashed_index: Index of the slashed validator
        block: Optional block for sync committee reward/penalty calculations (Altair+)
        proposer_slashing: Optional ProposerSlashing for GLOAS builder payment checks

    Checks performed:
        - validators[slashed_index].slashed == True
        - validators[slashed_index].exit_epoch set correctly
        - validators[slashed_index].withdrawable_epoch set correctly
        - slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] incremented by effective_balance
        - balances[slashed_index] decreased by slash penalty
        - balances[proposer_index] increased by whistleblower reward
        - [GLOAS+] builder_pending_payments entry cleared if the slashed validator is the
          payment's proposer and the header slot is within the 2-epoch window; left intact
          otherwise
    """
    current_epoch = spec.get_current_epoch(state)
    pre_validator = pre_state.validators[slashed_index]
    post_validator = state.validators[slashed_index]

    # Verify slashed flag
    assert post_validator.slashed

    # Verify exit_epoch
    if pre_validator.exit_epoch == spec.FAR_FUTURE_EPOCH:
        min_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
        assert post_validator.exit_epoch >= min_exit_epoch
    else:
        assert post_validator.exit_epoch == pre_validator.exit_epoch

    # Verify withdrawable_epoch
    expected_withdrawable_from_exit = (
        post_validator.exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    expected_withdrawable_from_slashing = current_epoch + spec.EPOCHS_PER_SLASHINGS_VECTOR
    expected_withdrawable = max(
        expected_withdrawable_from_exit, expected_withdrawable_from_slashing
    )
    if pre_validator.withdrawable_epoch != spec.FAR_FUTURE_EPOCH:
        expected_withdrawable = max(expected_withdrawable, pre_validator.withdrawable_epoch)
    assert post_validator.withdrawable_epoch == expected_withdrawable

    # Verify slashings array (only when proposer_slashing provided, to handle multiple slashings in same block)
    if proposer_slashing is not None:
        slashings_index = current_epoch % spec.EPOCHS_PER_SLASHINGS_VECTOR
        expected_slashings = pre_state.slashings[slashings_index] + pre_validator.effective_balance
        assert state.slashings[slashings_index] == expected_slashings

    # Verify balance changes
    proposer_index = spec.get_beacon_proposer_index(state)
    slash_penalty = post_validator.effective_balance // get_min_slashing_penalty_quotient(spec)
    whistleblower_reward = post_validator.effective_balance // get_whistleblower_reward_quotient(
        spec
    )

    sc_reward_for_slashed = sc_penalty_for_slashed = 0
    sc_reward_for_proposer = sc_penalty_for_proposer = 0
    if is_post_altair(spec) and block is not None:
        committee_indices = compute_committee_indices(state, state.current_sync_committee)
        committee_bits = block.body.sync_aggregate.sync_committee_bits
        sc_reward_for_slashed, sc_penalty_for_slashed = (
            compute_sync_committee_participant_reward_and_penalty(
                spec,
                pre_state,
                slashed_index,
                committee_indices,
                committee_bits,
            )
        )
        sc_reward_for_proposer, sc_penalty_for_proposer = (
            compute_sync_committee_participant_reward_and_penalty(
                spec,
                pre_state,
                proposer_index,
                committee_indices,
                committee_bits,
            )
        )

    if proposer_index != slashed_index:
        assert (
            get_balance(state, slashed_index)
            == get_balance(pre_state, slashed_index)
            - slash_penalty
            + sc_reward_for_slashed
            - sc_penalty_for_slashed
        )
        assert get_balance(state, proposer_index) >= (
            get_balance(pre_state, proposer_index)
            + whistleblower_reward
            + sc_reward_for_proposer
            - sc_penalty_for_proposer
        )
    else:
        assert get_balance(state, slashed_index) >= (
            get_balance(pre_state, slashed_index)
            - slash_penalty
            + whistleblower_reward
            + sc_reward_for_slashed
            - sc_penalty_for_slashed
        )

    # GLOAS: Verify builder pending payments
    if is_post_gloas(spec) and proposer_slashing is not None:
        header_slot = proposer_slashing.signed_header_1.message.slot
        proposal_epoch = spec.compute_epoch_at_slot(header_slot)

        if proposal_epoch == current_epoch:
            payment_index = spec.SLOTS_PER_EPOCH + header_slot % spec.SLOTS_PER_EPOCH
        elif proposal_epoch == spec.get_previous_epoch(state):
            payment_index = header_slot % spec.SLOTS_PER_EPOCH
        else:
            payment_index = None

        if payment_index is None:
            # Slot is outside the 2-epoch window: payments are untouched
            assert state.builder_pending_payments == pre_state.builder_pending_payments
        elif pre_state.builder_pending_payments[payment_index].proposer_index == slashed_index:
            # The slashed validator is this payment's proposer, so it is cleared
            assert state.builder_pending_payments[payment_index] == spec.BuilderPendingPayment()
        else:
            # This payment has a different proposer, so it is left intact
            assert (
                state.builder_pending_payments[payment_index]
                == pre_state.builder_pending_payments[payment_index]
            )


def get_valid_proposer_slashing(
    spec,
    state,
    random_root=b"\x99" * 32,
    slashed_index=None,
    slot=None,
    signed_1=False,
    signed_2=False,
):
    if slashed_index is None:
        current_epoch = spec.get_current_epoch(state)
        slashed_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validators[slashed_index].pubkey]
    if slot is None:
        slot = state.slot

    header_1 = spec.BeaconBlockHeader(
        slot=slot,
        proposer_index=slashed_index,
        parent_root=b"\x33" * 32,
        state_root=b"\x44" * 32,
        body_root=b"\x55" * 32,
    )
    header_2 = header_1.copy()
    header_2.parent_root = random_root

    if signed_1:
        signed_header_1 = sign_block_header(spec, state, header_1, privkey)
    else:
        signed_header_1 = spec.SignedBeaconBlockHeader(message=header_1)
    if signed_2:
        signed_header_2 = sign_block_header(spec, state, header_2, privkey)
    else:
        signed_header_2 = spec.SignedBeaconBlockHeader(message=header_2)

    return spec.ProposerSlashing(
        signed_header_1=signed_header_1,
        signed_header_2=signed_header_2,
    )


def get_valid_proposer_slashings(spec, state, num_slashings):
    proposer_slashings = []
    for i in range(num_slashings):
        slashed_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[i]
        assert not state.validators[slashed_index].slashed

        proposer_slashing = get_valid_proposer_slashing(
            spec, state, slashed_index=slashed_index, signed_1=True, signed_2=True
        )
        proposer_slashings.append(proposer_slashing)
    return proposer_slashings


def run_proposer_slashing_processing(spec, state, proposer_slashing, valid=True):
    """
    Run process_proposer_slashing, yielding pre/post states for test vectors.

    Unlike the phase0 version, this does NOT call check_proposer_slashing_effect
    (use assert_process_proposer_slashing for that).

    Args:
        spec: The spec object
        state: The beacon state (modified in place for valid slashings)
        proposer_slashing: The proposer slashing operation
        valid: If True, expect success. If False, expect error (AssertionError or IndexError).
    """
    yield "pre", state
    yield "proposer_slashing", proposer_slashing

    if valid:
        spec.process_proposer_slashing(state, proposer_slashing)
        yield "post", state
    else:
        # Catch both AssertionError (from assert statements) and IndexError (from invalid indices)
        with pytest.raises((AssertionError, IndexError)):
            spec.process_proposer_slashing(state, proposer_slashing)
        yield "post", None


def prepare_process_proposer_slashing(
    spec,
    state,
    # Epoch advancement
    advance_epochs=None,  # Epochs to advance before setup
    advance_epochs_after=None,  # Epochs to advance after creating slashing
    # Slot configuration (slot_1 = state.slot + slot_offset after advance_epochs)
    slot_offset=0,  # Offset from state.slot for header 1
    slot_2=None,  # Explicit slot for header 2 (default: same as header 1)
    # Proposer configuration
    proposer_index=None,  # Proposer index for header 1 (default: last active validator)
    proposer_index_2=None,  # Proposer index for header 2 (default: same as header 1)
    # Header roots (header 2 defaults to same as header 1)
    parent_root=None,  # Parent root for header 1 (default: b"\x33" * 32)
    parent_root_2=None,  # Parent root for header 2 (default: same as header 1)
    state_root=None,  # State root for header 1 (default: b"\x44" * 32)
    state_root_2=None,  # State root for header 2 (default: same as header 1)
    body_root=None,  # Body root for header 1 (default: b"\x55" * 32)
    body_root_2=None,  # Body root for header 2 (default: same as header 1)
    # Signature configuration
    signed_1=True,  # Sign header 1 with valid BLS signature
    signed_2=True,  # Sign header 2 with valid BLS signature
    # Proposer state configuration (applies to validator at proposer_index)
    proposer_slashed=None,  # Set proposer's slashed flag
    proposer_activation_epoch_offset=None,  # activation_epoch = current_epoch + offset
    proposer_withdrawable_epoch_offset=None,  # withdrawable_epoch = current_epoch + offset
    proposer_exit_epoch_offset=None,  # exit_epoch = current_epoch + offset
    proposer_balance=None,  # Set proposer balance
    proposer_effective_balance=None,  # Set proposer effective balance
    # GLOAS builder payment configuration
    builder_payment_amount=None,  # Amount for builder pending payment
    builder_payment_fee_recipient=None,  # Fee recipient address (20 bytes)
    builder_payment_weight=None,  # Weight for the pending payment (default: 0)
    builder_payment_builder_index=None,  # Builder index for the payment (default: last builder)
    builder_payment_proposer_index=None,  # Proposer recorded on the payment (default: slashed proposer)
):
    """
    Prepare a proposer slashing operation with configurable headers and state.

    Slot calculation:
        slot_1 = state.slot + slot_offset  (after advance_epochs)
        slot_2 = slot_2 if provided, else slot_1

    By default, both headers are IDENTICAL, which means the slashing would be
    invalid. To create a valid slashing, make the headers different
    (e.g., set parent_root_2=b"\\x99" * 32).

    Returns:
        Tuple[ProposerSlashing, ValidatorIndex]: The slashing operation and slashed validator index
    """
    if advance_epochs is not None:
        for _ in range(advance_epochs):
            next_epoch(spec, state)

    effective_slot_1 = state.slot + slot_offset
    effective_slot_2 = slot_2 if slot_2 is not None else effective_slot_1

    current_epoch = spec.get_current_epoch(state)
    if proposer_index is not None:
        effective_proposer_1 = proposer_index
    else:
        effective_proposer_1 = spec.get_active_validator_indices(state, current_epoch)[-1]

    effective_proposer_2 = (
        proposer_index_2 if proposer_index_2 is not None else effective_proposer_1
    )

    privkey = pubkey_to_privkey[state.validators[effective_proposer_1].pubkey]

    # Build header 1
    effective_parent_root = parent_root if parent_root is not None else b"\x33" * 32
    effective_state_root = state_root if state_root is not None else b"\x44" * 32
    effective_body_root = body_root if body_root is not None else b"\x55" * 32

    header_1 = spec.BeaconBlockHeader(
        slot=effective_slot_1,
        proposer_index=effective_proposer_1,
        parent_root=effective_parent_root,
        state_root=effective_state_root,
        body_root=effective_body_root,
    )

    # Build header 2 (defaults to same as header 1)
    effective_parent_root_2 = parent_root_2 if parent_root_2 is not None else effective_parent_root
    effective_state_root_2 = state_root_2 if state_root_2 is not None else effective_state_root
    effective_body_root_2 = body_root_2 if body_root_2 is not None else effective_body_root

    header_2 = spec.BeaconBlockHeader(
        slot=effective_slot_2,
        proposer_index=effective_proposer_2,
        parent_root=effective_parent_root_2,
        state_root=effective_state_root_2,
        body_root=effective_body_root_2,
    )

    if signed_1:
        signed_header_1 = sign_block_header(spec, state, header_1, privkey)
    else:
        signed_header_1 = spec.SignedBeaconBlockHeader(message=header_1)

    if signed_2:
        # Use privkey for header_2's proposer (may be different if proposer_index_2 differs)
        if proposer_index_2 is not None and proposer_index_2 != effective_proposer_1:
            privkey_2 = pubkey_to_privkey[state.validators[proposer_index_2].pubkey]
        else:
            privkey_2 = privkey
        signed_header_2 = sign_block_header(spec, state, header_2, privkey_2)
    else:
        signed_header_2 = spec.SignedBeaconBlockHeader(message=header_2)

    if proposer_slashed is not None:
        state.validators[effective_proposer_1].slashed = proposer_slashed

    if proposer_activation_epoch_offset is not None:
        state.validators[effective_proposer_1].activation_epoch = (
            current_epoch + proposer_activation_epoch_offset
        )

    if proposer_withdrawable_epoch_offset is not None:
        state.validators[effective_proposer_1].withdrawable_epoch = (
            current_epoch + proposer_withdrawable_epoch_offset
        )

    if proposer_exit_epoch_offset is not None:
        state.validators[effective_proposer_1].exit_epoch = (
            current_epoch + proposer_exit_epoch_offset
        )

    if proposer_balance is not None:
        state.balances[effective_proposer_1] = proposer_balance

    if proposer_effective_balance is not None:
        state.validators[effective_proposer_1].effective_balance = proposer_effective_balance

    # Set builder payment (GLOAS+)
    # Uses slot from header_1, consistent with spec's process_proposer_slashing
    if is_post_gloas(spec) and builder_payment_amount is not None:
        payment_slot = effective_slot_1
        payment_epoch = spec.compute_epoch_at_slot(payment_slot)

        # Calculate payment index based on what current_epoch will be after advance_epochs_after
        effective_current_epoch = current_epoch + (advance_epochs_after or 0)

        if payment_epoch == effective_current_epoch:
            payment_index = spec.SLOTS_PER_EPOCH + payment_slot % spec.SLOTS_PER_EPOCH
        elif payment_epoch == effective_current_epoch - 1:
            # Previous epoch
            payment_index = payment_slot % spec.SLOTS_PER_EPOCH
        else:
            # Outside 2-epoch window - skip payment setup
            payment_index = None

        if payment_index is not None:
            fee_recipient = (
                spec.ExecutionAddress(builder_payment_fee_recipient)
                if builder_payment_fee_recipient is not None
                else spec.ExecutionAddress(b"\x00" * 20)
            )
            weight = builder_payment_weight if builder_payment_weight is not None else 0
            builder_index = (
                spec.BuilderIndex(builder_payment_builder_index)
                if builder_payment_builder_index is not None
                else spec.BuilderIndex(len(state.builders) - 1)
            )

            pending_withdrawal = spec.BuilderPendingWithdrawal(
                fee_recipient=fee_recipient,
                amount=spec.Gwei(builder_payment_amount),
                builder_index=builder_index,
            )

            payment_proposer_index = (
                spec.ValidatorIndex(builder_payment_proposer_index)
                if builder_payment_proposer_index is not None
                else effective_proposer_1
            )

            pending_payment = spec.BuilderPendingPayment(
                weight=spec.Gwei(weight),
                withdrawal=pending_withdrawal,
                proposer_index=payment_proposer_index,
            )

            state.builder_pending_payments[payment_index] = pending_payment

    proposer_slashing = spec.ProposerSlashing(
        signed_header_1=signed_header_1,
        signed_header_2=signed_header_2,
    )

    if advance_epochs_after is not None:
        for _ in range(advance_epochs_after):
            next_epoch(spec, state)

    return proposer_slashing, effective_proposer_1


def assert_process_proposer_slashing(
    spec,
    state,
    pre_state,
    proposer_slashing=None,
    state_unchanged=False,
):
    """
    Assert expected outcomes from process_proposer_slashing.

    For invalid cases (where the function raises an exception), use state_unchanged=True.
    For valid cases, delegates to check_proposer_slashing_effect for all invariant checks.

    Args:
        spec: The spec module for the fork being tested
        state: State after slashing was processed
        pre_state: State before slashing was processed
        proposer_slashing: Required when state_unchanged=False
        state_unchanged: If True, asserts state equals pre_state (for rejected slashings)
    """
    if state_unchanged:
        assert state == pre_state, "Expected state to be unchanged after rejected slashing"
        return

    assert proposer_slashing is not None, "proposer_slashing required when state_unchanged=False"
    slashed_index = proposer_slashing.signed_header_1.message.proposer_index
    check_proposer_slashing_effect(
        spec, pre_state, state, slashed_index, proposer_slashing=proposer_slashing
    )
