from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_electra,
    is_post_gloas,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.state import get_balance
from eth2spec.test.helpers.sync_committee import (
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
        - [GLOAS+] builder_pending_payments cleared if header slot within 2-epoch window
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
            assert state.builder_pending_payments[payment_index] == spec.BuilderPendingPayment()
        elif proposal_epoch == spec.get_previous_epoch(state):
            payment_index = header_slot % spec.SLOTS_PER_EPOCH
            assert state.builder_pending_payments[payment_index] == spec.BuilderPendingPayment()
        else:
            assert state.builder_pending_payments == pre_state.builder_pending_payments


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
