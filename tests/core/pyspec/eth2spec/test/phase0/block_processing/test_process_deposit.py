from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls, with_all_phases
from eth2spec.test.helpers.deposits import (
    build_deposit,
    prepare_state_and_deposit,
    sign_deposit_data,
    deposit_from_context)
from eth2spec.test.helpers.state import get_balance
from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.utils import bls


def run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=True):
    """
    Run ``process_deposit``, yielding:
      - pre-state ('pre')
      - deposit ('deposit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_validator_count = len(state.validators)
    pre_balance = 0
    if validator_index < pre_validator_count:
        pre_balance = get_balance(state, validator_index)

    yield 'pre', state
    yield 'deposit', deposit

    if not valid:
        expect_assertion_error(lambda: spec.process_deposit(state, deposit))
        yield 'post', None
        return

    spec.process_deposit(state, deposit)

    yield 'post', state

    if not effective:
        assert len(state.validators) == pre_validator_count
        assert len(state.balances) == pre_validator_count
        if validator_index < pre_validator_count:
            assert get_balance(state, validator_index) == pre_balance
    else:
        if validator_index < pre_validator_count:
            # top-up
            assert len(state.validators) == pre_validator_count
            assert len(state.balances) == pre_validator_count
        else:
            # new validator
            assert len(state.validators) == pre_validator_count + 1
            assert len(state.balances) == pre_validator_count + 1
        assert get_balance(state, validator_index) == pre_balance + deposit.data.amount

        effective = min(spec.MAX_EFFECTIVE_BALANCE,
                        pre_balance + deposit.data.amount)
        effective -= effective % spec.EFFECTIVE_BALANCE_INCREMENT
        assert state.validators[validator_index].effective_balance == effective

    assert state.eth1_deposit_index == state.eth1_data.deposit_count


@with_all_phases
@spec_state_test
def test_new_deposit_under_max(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be 1 EFFECTIVE_BALANCE_INCREMENT smaller because of this small decrement.
    amount = spec.MAX_EFFECTIVE_BALANCE - 1
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_new_deposit_max(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_new_deposit_over_max(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # just 1 over the limit, effective balance should be set MAX_EFFECTIVE_BALANCE during processing
    amount = spec.MAX_EFFECTIVE_BALANCE + 1
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_new_deposit_eth1_withdrawal_credentials(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(
        spec, state,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_new_deposit_non_versioned_withdrawal_credentials(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        b'\xFF'  # Non specified withdrawal credentials version
        + b'\x02' * 31  # Garabage bytes
    )
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(
        spec, state,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_sig_other_version(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    # Go through the effort of manually signing, not something normally done. This sig domain will be invalid.
    deposit_message = spec.DepositMessage(pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount)
    domain = spec.compute_domain(domain_type=spec.DOMAIN_DEPOSIT, fork_version=spec.Version('0xaabbccdd'))
    deposit_data = spec.DepositData(
        pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount,
        signature=bls.Sign(privkey, spec.compute_signing_root(deposit_message, domain))
    )
    deposit, root, _ = deposit_from_context(spec, [deposit_data], 0)

    state.eth1_deposit_index = 0
    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count = 1

    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=False)


@with_all_phases
@spec_state_test
@always_bls
def test_valid_sig_but_forked_state(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    # deposits will always be valid, regardless of the current fork
    state.fork.current_version = spec.Version('0x1234abcd')
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)
    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=True)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_sig_new_deposit(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)
    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=False)


@with_all_phases
@spec_state_test
def test_success_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_sig_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)

    # invalid signatures, in top-ups, are allowed!
    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=True)


@with_all_phases
@spec_state_test
def test_invalid_withdrawal_credentials_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(b"junk")[1:]
    deposit = prepare_state_and_deposit(
        spec,
        state,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials
    )

    # inconsistent withdrawal credentials, in top-ups, are allowed!
    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=True)


@with_all_phases
@spec_state_test
def test_wrong_deposit_for_deposit_count(spec, state):
    deposit_data_leaves = [spec.DepositData() for _ in range(len(state.validators))]

    # build root for deposit_1
    index_1 = len(deposit_data_leaves)
    pubkey_1 = pubkeys[index_1]
    privkey_1 = privkeys[index_1]
    _, _, deposit_data_leaves = build_deposit(
        spec,
        deposit_data_leaves,
        pubkey_1,
        privkey_1,
        spec.MAX_EFFECTIVE_BALANCE,
        withdrawal_credentials=b'\x00' * 32,
        signed=True,
    )
    deposit_count_1 = len(deposit_data_leaves)

    # build root for deposit_2
    index_2 = len(deposit_data_leaves)
    pubkey_2 = pubkeys[index_2]
    privkey_2 = privkeys[index_2]
    deposit_2, root_2, deposit_data_leaves = build_deposit(
        spec,
        deposit_data_leaves,
        pubkey_2,
        privkey_2,
        spec.MAX_EFFECTIVE_BALANCE,
        withdrawal_credentials=b'\x00' * 32,
        signed=True,
    )

    # state has root for deposit_2 but is at deposit_count for deposit_1
    state.eth1_data.deposit_root = root_2
    state.eth1_data.deposit_count = deposit_count_1

    yield from run_deposit_processing(spec, state, deposit_2, index_2, valid=False)


@with_all_phases
@spec_state_test
def test_bad_merkle_proof(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)

    # mess up merkle branch
    deposit.proof[5] = spec.Bytes32()

    sign_deposit_data(spec, deposit.data, privkeys[validator_index])

    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=False)
