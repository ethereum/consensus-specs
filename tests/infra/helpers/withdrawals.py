from tests.core.pyspec.eth2spec.test.helpers.forks import is_post_electra, is_post_gloas


def get_expected_withdrawals(spec, state):
    if is_post_gloas(spec):
        withdrawals, _, _ = spec.get_expected_withdrawals(state)
        return withdrawals
    elif is_post_electra(spec):
        withdrawals, _ = spec.get_expected_withdrawals(state)
        return withdrawals
    else:
        return spec.get_expected_withdrawals(state)


def verify_withdrawals_post_state(
    spec,
    pre_state,
    post_state,
    execution_payload,
    expected_withdrawals,
    fully_withdrawable_indices,
    partial_withdrawals_indices,
    pending_withdrawal_requests,
):
    """
    Verifies the correctness of the post-state after processing withdrawals.
    """

    # Since gloas, if parent block was not full, no withdrawals processed, indices unchanged
    if is_post_gloas(spec) and not spec.is_parent_block_full(pre_state):
        assert post_state.next_withdrawal_index == pre_state.next_withdrawal_index
        assert (
            post_state.next_withdrawal_validator_index == pre_state.next_withdrawal_validator_index
        )
        return

    _verify_withdrawals_next_withdrawal_index(spec, pre_state, post_state, expected_withdrawals)

    # Verify withdrawals indexes
    for index, withdrawal in enumerate(
        expected_withdrawals if is_post_gloas(spec) else execution_payload.withdrawals
    ):
        assert withdrawal.index == pre_state.next_withdrawal_index + index

    if fully_withdrawable_indices is not None or partial_withdrawals_indices is not None:
        _verify_withdrawals_post_state_balances(
            spec,
            post_state,
            expected_withdrawals,
            fully_withdrawable_indices,
            partial_withdrawals_indices,
        )

    # Check withdrawal requests
    if pending_withdrawal_requests is not None:
        _verify_withdrawals_requests(execution_payload, pending_withdrawal_requests)


def _verify_withdrawals_next_withdrawal_index(spec, pre_state, post_state, expected_withdrawals):
    """
    Verify post_state.next_withdrawal_index
    """
    assert post_state.next_withdrawal_index == pre_state.next_withdrawal_index + len(
        expected_withdrawals
    )
    if len(expected_withdrawals) == 0:
        assert post_state.next_withdrawal_index == pre_state.next_withdrawal_index
    elif len(expected_withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        latest_withdrawal = expected_withdrawals[-1]
        assert post_state.next_withdrawal_index == latest_withdrawal.index + 1

        # variable expected_withdrawals comes from pre_state
        assert expected_withdrawals != get_expected_withdrawals(spec, post_state)
        bound = min(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        assert len(get_expected_withdrawals(spec, post_state)) <= bound
    else:
        raise ValueError(
            "len(expected_withdrawals) should not be greater than MAX_WITHDRAWALS_PER_PAYLOAD"
        )

    # Verify post_state.next_withdrawal_validator_index
    if len(expected_withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        if is_post_gloas(spec):
            validator_pubkeys = [v.pubkey for v in post_state.validators]
            index = validator_pubkeys.index(expected_withdrawals[-1].pubkey)
        else:
            index = expected_withdrawals[-1].validator_index
        next_validator_index = (index + 1) % len(post_state.validators)
        assert post_state.next_withdrawal_validator_index == next_validator_index
    else:
        # Advance sweep by the max length if there was not a full set of withdrawals
        next_index = (
            pre_state.next_withdrawal_validator_index + spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        )
        next_validator_index = next_index % len(post_state.validators)
        assert post_state.next_withdrawal_validator_index == next_validator_index


def _verify_withdrawals_post_state_balances(
    spec, state, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices
):
    if len(expected_withdrawals) == 0:
        return

    expected_withdrawals_validator_indices = [
        withdrawal.validator_index for withdrawal in expected_withdrawals
    ]

    for index in fully_withdrawable_indices:
        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == 0
        else:
            assert state.balances[index] > 0
    for index in partial_withdrawals_indices:
        if is_post_electra(spec):
            max_effective_balance = spec.get_max_effective_balance(state.validators[index])
        else:
            max_effective_balance = spec.MAX_EFFECTIVE_BALANCE

        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == max_effective_balance
        else:
            assert state.balances[index] > max_effective_balance


def _verify_withdrawals_requests(execution_payload, pending_withdrawal_requests):
    assert len(pending_withdrawal_requests) <= len(execution_payload.withdrawals)
    for index, request in enumerate(pending_withdrawal_requests):
        withdrawal = execution_payload.withdrawals[index]
        assert withdrawal.validator_index == request.validator_index
        assert withdrawal.amount == request.amount
