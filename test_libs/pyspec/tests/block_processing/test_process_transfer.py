import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_active_validator_indices,
    get_beacon_proposer_index,
    get_current_epoch,
    process_transfer,
)
from tests.helpers import (
    get_valid_transfer,
    next_epoch,
)

from .block_test_helpers import spec_state_test


def run_transfer_processing(state, transfer, valid=True):
    """
    Run ``process_transfer``, yielding:
      - pre-state ('pre')
      - transfer ('transfer')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    proposer_index = get_beacon_proposer_index(state)
    pre_transfer_sender_balance = state.balances[transfer.sender]
    pre_transfer_recipient_balance = state.balances[transfer.recipient]
    pre_transfer_proposer_balance = state.balances[proposer_index]

    yield 'pre', state
    yield 'transfer', transfer

    if not valid:
        with pytest.raises(AssertionError):
            process_transfer(state, transfer)
        yield 'post', None
        return

    process_transfer(state, transfer)
    yield 'post', state

    sender_balance = state.balances[transfer.sender]
    recipient_balance = state.balances[transfer.recipient]
    assert sender_balance == pre_transfer_sender_balance - transfer.amount - transfer.fee
    assert recipient_balance == pre_transfer_recipient_balance + transfer.amount
    assert state.balances[proposer_index] == pre_transfer_proposer_balance + transfer.fee


@spec_state_test
def test_success_non_activated(state):
    transfer = get_valid_transfer(state)
    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(state, transfer)


@spec_state_test
def test_success_withdrawable(state):
    next_epoch(state)

    transfer = get_valid_transfer(state)

    # withdrawable_epoch in past so can transfer
    state.validator_registry[transfer.sender].withdrawable_epoch = get_current_epoch(state) - 1

    yield from run_transfer_processing(state, transfer)


@spec_state_test
def test_success_active_above_max_effective(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE // 32
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE + amount
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=amount, fee=0)

    yield from run_transfer_processing(state, transfer)


@spec_state_test
def test_active_but_transfer_past_effective_balance(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE // 32
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=amount, fee=0)

    yield from run_transfer_processing(state, transfer, False)


@spec_state_test
def test_incorrect_slot(state):
    transfer = get_valid_transfer(state, slot=state.slot+1)
    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(state, transfer, False)


@spec_state_test
def test_insufficient_balance(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=amount + 1, fee=0)

    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(state, transfer, False)


@spec_state_test
def test_no_dust(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    balance = state.balances[sender_index]
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=balance - spec.MIN_DEPOSIT_AMOUNT + 1, fee=0)

    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(state, transfer, False)


@spec_state_test
def test_invalid_pubkey(state):
    transfer = get_valid_transfer(state)
    state.validator_registry[transfer.sender].withdrawal_credentials = spec.ZERO_HASH

    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    yield from run_transfer_processing(state, transfer, False)
