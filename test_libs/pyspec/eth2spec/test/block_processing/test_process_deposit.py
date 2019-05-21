import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import process_deposit
from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls
from eth2spec.test.helpers.deposits import prepare_state_and_deposit, sign_deposit_data
from eth2spec.test.helpers.state import get_balance
from eth2spec.test.helpers.keys import privkeys


def run_deposit_processing(state, deposit, validator_index, valid=True, non_effective=False):
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
        expect_assertion_error(lambda: process_deposit(state, deposit))
        yield 'post', None
        return

    process_deposit(state, deposit)

    yield 'post', state

    if non_effective:
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
    deposit = prepare_state_and_deposit(state, validator_index, amount, signed=False)
    yield from run_deposit_processing(state, deposit, validator_index, valid=True, non_effective=True)


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
    deposit = prepare_state_and_deposit(state, validator_index, amount, signed=False)

    # invalid signatures, in top-ups, are allowed!
    yield from run_deposit_processing(state, deposit, validator_index, valid=True, non_effective=False)


@spec_state_test
def test_wrong_index(state):
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount, signed=False)

    # mess up deposit_index
    deposit.index = state.deposit_index + 1

    sign_deposit_data(state, deposit.data, privkeys[validator_index])

    yield from run_deposit_processing(state, deposit, validator_index, valid=False)


# TODO: test invalid signature


@spec_state_test
def test_bad_merkle_proof(state):
    validator_index = len(state.validator_registry)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(state, validator_index, amount, signed=False)

    # mess up merkle branch
    deposit.proof[-1] = spec.ZERO_HASH

    sign_deposit_data(state, deposit.data, privkeys[validator_index])

    yield from run_deposit_processing(state, deposit, validator_index, valid=False)
