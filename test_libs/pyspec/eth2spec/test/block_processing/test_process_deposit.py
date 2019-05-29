import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import process_deposit
from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls
from eth2spec.test.helpers.deposits import (
    build_deposit,
    prepare_state_and_deposit,
    sign_deposit_data,
)
from eth2spec.test.helpers.state import get_balance
from eth2spec.test.helpers.keys import privkeys, pubkeys


def run_deposit_processing(state, deposit, validator_index, valid=True, effective=True):
    """
    Run ``process_deposit``, yielding:
      - pre-state ('pre')
      - deposit ('deposit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_validator_count = len(state.validator_registry)
    pre_balance = 0
    if validator_index < pre_validator_count:
        pre_balance = get_balance(state, validator_index)

    yield 'pre', state
    yield 'deposit', deposit

    if not valid:
        expect_assertion_error(lambda: process_deposit(state, deposit))
        yield 'post', None
        return

    process_deposit(state, deposit)

    yield 'post', state

    if not effective:
        assert len(state.validator_registry) == pre_validator_count
        assert len(state.balances) == pre_validator_count
        if validator_index < pre_validator_count:
            assert get_balance(state, validator_index) == pre_balance
    else:
        if validator_index < pre_validator_count:
            # top-up
            assert len(state.validator_registry) == pre_validator_count
            assert len(state.balances) == pre_validator_count
        else:
            # new validator
            assert len(state.validator_registry) == pre_validator_count + 1
            assert len(state.balances) == pre_validator_count + 1
        assert get_balance(state, validator_index) == pre_balance + deposit.data.amount

    assert state.deposit_index == state.latest_eth1_data.deposit_count


@spec_state_test
def test_new_deposit(state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount, signed=True)

    yield from run_deposit_processing(state, deposit, validator_index)


@always_bls
@spec_state_test
def test_invalid_sig_new_deposit(state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount)
    yield from run_deposit_processing(state, deposit, validator_index, valid=True, effective=False)


@spec_state_test
def test_success_top_up(state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(state, validator_index, amount, signed=True)

    yield from run_deposit_processing(state, deposit, validator_index)


@always_bls
@spec_state_test
def test_invalid_sig_top_up(state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    # invalid signatures, in top-ups, are allowed!
    yield from run_deposit_processing(state, deposit, validator_index, valid=True, effective=True)


@spec_state_test
def test_wrong_index(state):
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    # mess up deposit_index
    deposit.index = state.deposit_index + 1

    sign_deposit_data(state, deposit.data, privkeys[validator_index])

    yield from run_deposit_processing(state, deposit, validator_index, valid=False)


@spec_state_test
def test_wrong_deposit_for_deposit_count(state):
    deposit_data_leaves = [spec.ZERO_HASH] * len(state.validator_registry)

    # build root for deposit_1
    index_1 = len(deposit_data_leaves)
    pubkey_1 = pubkeys[index_1]
    privkey_1 = privkeys[index_1]
    deposit_1, root_1, deposit_data_leaves = build_deposit(
        state,
        deposit_data_leaves,
        pubkey_1,
        privkey_1,
        spec.MAX_EFFECTIVE_BALANCE,
        signed=True,
    )
    deposit_count_1 = len(deposit_data_leaves)

    # build root for deposit_2
    index_2 = len(deposit_data_leaves)
    pubkey_2 = pubkeys[index_2]
    privkey_2 = privkeys[index_2]
    deposit_2, root_2, deposit_data_leaves = build_deposit(
        state,
        deposit_data_leaves,
        pubkey_2,
        privkey_2,
        spec.MAX_EFFECTIVE_BALANCE,
        signed=True,
    )

    # state has root for deposit_2 but is at deposit_count for deposit_1
    state.latest_eth1_data.deposit_root = root_2
    state.latest_eth1_data.deposit_count = deposit_count_1

    yield from run_deposit_processing(state, deposit_2, index_2, valid=False)


# TODO: test invalid signature


@spec_state_test
def test_bad_merkle_proof(state):
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    # mess up merkle branch
    deposit.proof[-1] = spec.ZERO_HASH

    sign_deposit_data(state, deposit.data, privkeys[validator_index])

    yield from run_deposit_processing(state, deposit, validator_index, valid=False)
