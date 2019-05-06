import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    ZERO_HASH,
    process_deposit,
)
from tests.helpers import (
    get_balance,
    build_deposit,
    prepare_state_and_deposit,
    privkeys,
    pubkeys,
)

from tests.context import spec_state_test


def run_deposit_processing(state, deposit, validator_index, valid=True):
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
    else:
        # if it is a new validator, it should be right at the end of the current registry.
        assert validator_index == pre_validator_count

    yield 'pre', state
    yield 'deposit', deposit

    if not valid:
        with pytest.raises(AssertionError):
            process_deposit(state, deposit)
        yield 'post', None
        return

    process_deposit(state, deposit)

    yield 'post', state

    if validator_index < pre_validator_count:
        # top-up
        assert len(state.validator_registry) == pre_validator_count
        assert len(state.balances) == pre_validator_count
    else:
        # new validator
        assert len(state.validator_registry) == pre_validator_count + 1
        assert len(state.balances) == pre_validator_count + 1

    assert state.deposit_index == state.latest_eth1_data.deposit_count
    assert get_balance(state, validator_index) == pre_balance + deposit.data.amount


@spec_state_test
def test_success(state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    yield from run_deposit_processing(state, deposit, validator_index)


@spec_state_test
def test_success_top_up(state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    yield from run_deposit_processing(state, deposit, validator_index)


@spec_state_test
def test_wrong_index(state):
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    # mess up deposit_index
    deposit.index = state.deposit_index + 1

    yield from run_deposit_processing(state, deposit, validator_index, valid=False)


@spec_state_test
def test_bad_merkle_proof(state):
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount)

    # mess up merkle branch
    deposit.proof[-1] = spec.ZERO_HASH

    yield from run_deposit_processing(state, deposit, validator_index, valid=False)
