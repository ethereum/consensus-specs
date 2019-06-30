from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls, with_all_phases
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.helpers.transfers import get_valid_transfer, sign_transfer


def run_transfer_processing(spec, state, transfer, valid=True):
    """
    Run ``process_transfer``, yielding:
      - pre-state ('pre')
      - transfer ('transfer')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    yield 'pre', state
    yield 'transfer', transfer

    if not valid:
        expect_assertion_error(lambda: spec.process_transfer(state, transfer))
        yield 'post', None
        return

    proposer_index = spec.get_proposer_index(state)
    pre_transfer_sender_balance = state.balances[transfer.sender]
    pre_transfer_recipient_balance = state.balances[transfer.recipient]
    pre_transfer_proposer_balance = state.balances[proposer_index]

    spec.process_transfer(state, transfer)
    yield 'post', state

    sender_balance = state.balances[transfer.sender]
    recipient_balance = state.balances[transfer.recipient]
    assert sender_balance == pre_transfer_sender_balance - transfer.amount - transfer.fee
    assert recipient_balance == pre_transfer_recipient_balance + transfer.amount
    assert state.balances[proposer_index] == pre_transfer_proposer_balance + transfer.fee


@with_all_phases
@spec_state_test
def test_success_non_activated(spec, state):
    transfer = get_valid_transfer(spec, state, signed=True)
    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer)


@with_all_phases
@spec_state_test
def test_success_withdrawable(spec, state):
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    transfer = get_valid_transfer(spec, state, signed=True)

    # withdrawable_epoch in past so can transfer
    state.validators[transfer.sender].withdrawable_epoch = spec.get_current_epoch(state) - 1

    yield from run_transfer_processing(spec, state, transfer)


@with_all_phases
@spec_state_test
def test_success_active_above_max_effective(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=1, fee=0, signed=True)

    yield from run_transfer_processing(spec, state, transfer)


@with_all_phases
@spec_state_test
def test_success_active_above_max_effective_fee(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=0, fee=1, signed=True)

    yield from run_transfer_processing(spec, state, transfer)


@with_all_phases
@always_bls
@spec_state_test
def test_invalid_signature(spec, state):
    transfer = get_valid_transfer(spec, state)
    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_active_but_transfer_past_effective_balance(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE // 32
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=amount, fee=0, signed=True)

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_incorrect_slot(spec, state):
    transfer = get_valid_transfer(spec, state, slot=state.slot + 1, signed=True)
    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_transfer_clean(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=spec.MIN_DEPOSIT_AMOUNT, fee=0, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer)


@with_all_phases
@spec_state_test
def test_transfer_clean_split_to_fee(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=spec.MIN_DEPOSIT_AMOUNT // 2, fee=spec.MIN_DEPOSIT_AMOUNT // 2, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_fee(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=0, fee=1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_fee_result_full(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=0, fee=state.balances[sender_index] + 1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_amount_result_dust(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=1, fee=0, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_amount_result_full(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=state.balances[sender_index] + 1, fee=0, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_combined_result_dust(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee without dust, and amount without dust, but not both.
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=1, fee=1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_combined_result_full(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee fully without dust left, and amount fully without dust left, but not both.
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT * 2 + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=spec.MIN_DEPOSIT_AMOUNT + 1,
                                  fee=spec.MIN_DEPOSIT_AMOUNT + 1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_combined_big_amount(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee fully without dust left, and amount fully without dust left, but not both.
    # Try to create a dust balance (off by 1) with combination of fee and amount.
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT * 2 + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=spec.MIN_DEPOSIT_AMOUNT + 1, fee=1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_for_combined_big_fee(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee fully without dust left, and amount fully without dust left, but not both.
    # Try to create a dust balance (off by 1) with combination of fee and amount.
    state.balances[sender_index] = spec.MIN_DEPOSIT_AMOUNT * 2 + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=1, fee=spec.MIN_DEPOSIT_AMOUNT + 1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_off_by_1_fee(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee fully without dust left, and amount fully without dust left, but not both.
    # Try to print money by using the full balance as amount, plus 1 for fee.
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=state.balances[sender_index], fee=1, signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_off_by_1_amount(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee fully without dust left, and amount fully without dust left, but not both.
    # Try to print money by using the full balance as fee, plus 1 for amount.
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=1,
                                  fee=state.balances[sender_index], signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_insufficient_balance_duplicate_as_fee_and_amount(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    # Enough to pay fee fully without dust left, and amount fully without dust left, but not both.
    # Try to print money by using the full balance, twice.
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  amount=state.balances[sender_index],
                                  fee=state.balances[sender_index], signed=True)

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_no_dust_sender(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    balance = state.balances[sender_index]
    transfer = get_valid_transfer(
        spec,
        state,
        sender_index=sender_index,
        amount=balance - spec.MIN_DEPOSIT_AMOUNT + 1,
        fee=0,
        signed=True,
    )

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_no_dust_recipient(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=1, fee=0, signed=True)
    state.balances[transfer.recipient] = 0

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_non_existent_sender(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    transfer = get_valid_transfer(spec, state, sender_index=sender_index, amount=1, fee=0)
    transfer.sender = len(state.validators)
    sign_transfer(spec, state, transfer, 42)  # mostly valid signature, but sender won't exist, use bogus key.

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_non_existent_recipient(spec, state):
    sender_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE + 1
    transfer = get_valid_transfer(spec, state, sender_index=sender_index,
                                  recipient_index=len(state.validators), amount=1, fee=0, signed=True)

    yield from run_transfer_processing(spec, state, transfer, False)


@with_all_phases
@spec_state_test
def test_invalid_pubkey(spec, state):
    transfer = get_valid_transfer(spec, state, signed=True)
    state.validators[transfer.sender].withdrawal_credentials = spec.Hash()

    # un-activate so validator can transfer
    state.validators[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(spec, state, transfer, False)
