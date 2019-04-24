from copy import deepcopy
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


# mark entire file as 'transfers'
pytestmark = pytest.mark.transfers


def run_transfer_processing(state, transfer, valid=True):
    """
    Run ``process_transfer`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_transfer(post_state, transfer)
        return state, None


    process_transfer(post_state, transfer)

    proposer_index = get_beacon_proposer_index(state)
    pre_transfer_sender_balance = state.balances[transfer.sender]
    pre_transfer_recipient_balance = state.balances[transfer.recipient]
    pre_transfer_proposer_balance = state.balances[proposer_index]
    sender_balance = post_state.balances[transfer.sender]
    recipient_balance = post_state.balances[transfer.recipient]
    assert sender_balance == pre_transfer_sender_balance - transfer.amount - transfer.fee
    assert recipient_balance == pre_transfer_recipient_balance + transfer.amount
    assert post_state.balances[proposer_index] == pre_transfer_proposer_balance + transfer.fee

    return state, post_state


def test_success_non_activated(state):
    transfer = get_valid_transfer(state)
    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    pre_state, post_state = run_transfer_processing(state, transfer)

    return pre_state, transfer, post_state


def test_success_withdrawable(state):
    next_epoch(state)

    transfer = get_valid_transfer(state)

    # withdrawable_epoch in past so can transfer
    state.validator_registry[transfer.sender].withdrawable_epoch = get_current_epoch(state) - 1

    pre_state, post_state = run_transfer_processing(state, transfer)

    return pre_state, transfer, post_state


def test_success_active_above_max_effective(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE // 32
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE + amount
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=amount, fee=0)

    pre_state, post_state = run_transfer_processing(state, transfer)

    return pre_state, transfer, post_state


def test_active_but_transfer_past_effective_balance(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE // 32
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=amount, fee=0)

    pre_state, post_state = run_transfer_processing(state, transfer, False)

    return pre_state, transfer, post_state


def test_incorrect_slot(state):
    transfer = get_valid_transfer(state, slot=state.slot+1)
    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    pre_state, post_state = run_transfer_processing(state, transfer, False)

    return pre_state, transfer, post_state


def test_insufficient_balance(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    amount = spec.MAX_EFFECTIVE_BALANCE
    state.balances[sender_index] = spec.MAX_EFFECTIVE_BALANCE
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=amount + 1, fee=0)

    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    pre_state, post_state = run_transfer_processing(state, transfer, False)

    return pre_state, transfer, post_state


def test_no_dust(state):
    sender_index = get_active_validator_indices(state, get_current_epoch(state))[-1]
    balance = state.balances[sender_index]
    transfer = get_valid_transfer(state, sender_index=sender_index, amount=balance - spec.MIN_DEPOSIT_AMOUNT + 1, fee=0)

    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    pre_state, post_state = run_transfer_processing(state, transfer, False)

    return pre_state, transfer, post_state


def test_invalid_pubkey(state):
    transfer = get_valid_transfer(state)
    state.validator_registry[transfer.sender].withdrawal_credentials = spec.ZERO_HASH

    # un-activate so validator can transfer
    state.validator_registry[transfer.sender].activation_epoch = spec.FAR_FUTURE_EPOCH

    pre_state, post_state = run_transfer_processing(state, transfer, False)

    return pre_state, transfer, post_state
