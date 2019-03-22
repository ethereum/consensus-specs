from copy import deepcopy
import pytest

import build.phase0.spec as spec

from build.phase0.spec import (
    Deposit,
    get_balance,
    process_deposit,
)
from tests.phase0.helpers import (
    build_deposit,
)


# mark entire file as 'voluntary_exits'
pytestmark = pytest.mark.voluntary_exits


def test_success(state, deposit_data_leaves, pubkeys, privkeys):
    pre_state = deepcopy(state)

    index = len(deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_DEPOSIT_AMOUNT,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    process_deposit(post_state, deposit)

    assert len(post_state.validator_registry) == len(state.validator_registry) + 1
    assert len(post_state.balances) == len(state.balances) + 1
    assert post_state.validator_registry[index].pubkey == pubkeys[index]
    assert get_balance(post_state, index) == spec.MAX_DEPOSIT_AMOUNT
    assert post_state.deposit_index == post_state.latest_eth1_data.deposit_count

    return pre_state, deposit, post_state


def test_success_top_up(state, deposit_data_leaves, pubkeys, privkeys):
    pre_state = deepcopy(state)

    validator_index = 0
    amount = spec.MAX_DEPOSIT_AMOUNT // 4
    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        amount,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)
    pre_balance = get_balance(pre_state, validator_index)

    post_state = deepcopy(pre_state)

    process_deposit(post_state, deposit)

    assert len(post_state.validator_registry) == len(state.validator_registry)
    assert len(post_state.balances) == len(state.balances)
    assert post_state.deposit_index == post_state.latest_eth1_data.deposit_count
    assert get_balance(post_state, validator_index) == pre_balance + amount

    return pre_state, deposit, post_state


def test_wrong_index(state, deposit_data_leaves, pubkeys, privkeys):
    pre_state = deepcopy(state)

    index = len(deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_DEPOSIT_AMOUNT,
    )

    # mess up deposit_index
    deposit.index = pre_state.deposit_index + 1

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    with pytest.raises(AssertionError):
        process_deposit(post_state, deposit)

    return pre_state, deposit, None


def test_bad_merkle_proof(state, deposit_data_leaves, pubkeys, privkeys):
    pre_state = deepcopy(state)

    index = len(deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_DEPOSIT_AMOUNT,
    )

    # mess up merkle branch
    deposit.proof[-1] = spec.ZERO_HASH

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    with pytest.raises(AssertionError):
        process_deposit(post_state, deposit)

    return pre_state, deposit, None
