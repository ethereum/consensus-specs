from copy import deepcopy
import pytest


# mark entire file as 'deposits'
pytestmark = pytest.mark.deposits


def test_success(spec, helpers, state):
    pre_state = deepcopy(state)
    # fill previous deposits with zero-hash
    deposit_data_leaves = [spec.ZERO_HASH] * len(pre_state.validator_registry)

    index = len(deposit_data_leaves)
    pubkey = helpers.pubkeys[index]
    privkey = helpers.privkeys[index]
    deposit, root, deposit_data_leaves = helpers.build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        spec.MAX_EFFECTIVE_BALANCE,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    post_state = deepcopy(pre_state)

    spec.process_deposit(post_state, deposit)

    assert len(post_state.validator_registry) == len(state.validator_registry) + 1
    assert len(post_state.balances) == len(state.balances) + 1
    assert post_state.validator_registry[index].pubkey == helpers.pubkeys[index]
    assert helpers.get_balance(post_state, index) == spec.MAX_EFFECTIVE_BALANCE
    assert post_state.deposit_index == post_state.latest_eth1_data.deposit_count

    return pre_state, deposit, post_state


def test_success_top_up(spec, helpers, state):
    pre_state = deepcopy(state)
    deposit_data_leaves = [spec.ZERO_HASH] * len(pre_state.validator_registry)

    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    pubkey = helpers.pubkeys[validator_index]
    privkey = helpers.privkeys[validator_index]
    deposit, root, deposit_data_leaves = helpers.build_deposit(
        pre_state,
        deposit_data_leaves,
        pubkey,
        privkey,
        amount,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(deposit_data_leaves)
    pre_balance = helpers.get_balance(pre_state, validator_index)

    post_state = deepcopy(pre_state)

    spec.process_deposit(post_state, deposit)

    assert len(post_state.validator_registry) == len(state.validator_registry)
    assert len(post_state.balances) == len(state.balances)
    assert post_state.deposit_index == post_state.latest_eth1_data.deposit_count
    assert helpers.get_balance(post_state, validator_index) == pre_balance + amount

    return pre_state, deposit, post_state


def test_wrong_index(spec, helpers, state):
    pre_state = deepcopy(state)
    deposit_data_leaves = [spec.ZERO_HASH] * len(pre_state.validator_registry)

    index = len(deposit_data_leaves)
    pubkey = helpers.pubkeys[index]
    privkey = helpers.privkeys[index]
    deposit, root, deposit_data_leaves = helpers.build_deposit(
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
        spec.process_deposit(post_state, deposit)

    return pre_state, deposit, None


def test_bad_merkle_proof(spec, helpers, state):
    pre_state = deepcopy(state)
    deposit_data_leaves = [spec.ZERO_HASH] * len(pre_state.validator_registry)

    index = len(deposit_data_leaves)
    pubkey = helpers.pubkeys[index]
    privkey = helpers.privkeys[index]
    deposit, root, deposit_data_leaves = helpers.build_deposit(
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
        spec.process_deposit(post_state, deposit)

    return pre_state, deposit, None
