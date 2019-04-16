from copy import deepcopy
import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_balance,
    ZERO_HASH,
    process_deposit,
)
from phase0.helpers import (
    build_deposit,
    privkeys,
    pubkeys,
)


# mark entire file as 'deposits'
pytestmark = pytest.mark.deposits


def test_success(state):
    pre_state = deepcopy(state)
    # fill previous deposits with zero-hash
    deposit_data_leaves = [ZERO_HASH] * len(pre_state.validator_registry)

    index = len(deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_EFFECTIVE_BALANCE,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    process_deposit(post_state, deposit)

    assert len(post_state.validator_registry) == len(state.validator_registry) + 1
    assert len(post_state.balances) == len(state.balances) + 1
    assert post_state.validator_registry[index].pubkey == pubkeys[index]
    assert get_balance(post_state, index) == spec.MAX_EFFECTIVE_BALANCE
    assert post_state.deposit_index == post_state.latest_eth1_data.deposit_count

    return pre_state, deposit, post_state


def test_success_top_up(state):
    pre_state = deepcopy(state)
    deposit_data_leaves = [ZERO_HASH] * len(pre_state.validator_registry)

    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
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


def test_wrong_index(state):
    pre_state = deepcopy(state)
    deposit_data_leaves = [ZERO_HASH] * len(pre_state.validator_registry)

    index = len(deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_EFFECTIVE_BALANCE,
    )

    # mess up deposit_index
    deposit.index = pre_state.deposit_index + 1

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    with pytest.raises(AssertionError):
        process_deposit(post_state, deposit)

    return pre_state, deposit, None


def test_bad_merkle_proof(state):
    pre_state = deepcopy(state)
    deposit_data_leaves = [ZERO_HASH] * len(pre_state.validator_registry)

    index = len(deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit, root, deposit_data_leaves = build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_EFFECTIVE_BALANCE,
    )

    # mess up merkle branch
    deposit.proof[-1] = spec.ZERO_HASH

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    with pytest.raises(AssertionError):
        process_deposit(post_state, deposit)

    return pre_state, deposit, None
