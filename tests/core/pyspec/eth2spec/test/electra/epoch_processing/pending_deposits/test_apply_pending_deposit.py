from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
    always_bls,
)
from eth2spec.test.helpers.deposits import (
    prepare_pending_deposit,
    run_pending_deposit_applying,
)
from eth2spec.test.helpers.state import next_epoch_via_block
from eth2spec.test.helpers.withdrawals import set_validator_fully_withdrawable


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_under_min_activation(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be 1 EFFECTIVE_BALANCE_INCREMENT smaller because of this small decrement
    amount = spec.MIN_ACTIVATION_BALANCE - 1
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_min_activation(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_over_min_activation(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # just 1 over the limit, effective balance should be set MIN_ACTIVATION_BALANCE during processing
    amount = spec.MIN_ACTIVATION_BALANCE + 1
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_over_min_activation_next_increment(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # set deposit amount to the next effective balance increment over the limit
    # the validator's effective balance should be set to pre-electra MAX_EFFECTIVE_BALANCE
    amount = spec.MAX_EFFECTIVE_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    # check validator's effective balance
    assert state.validators[validator_index].effective_balance == spec.MAX_EFFECTIVE_BALANCE


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_eth1_withdrawal_credentials(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_compounding_withdrawal_credentials_under_max(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    # effective balance will be 1 EFFECTIVE_BALANCE_INCREMENT smaller because of this small decrement
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA - 1
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_compounding_withdrawal_credentials_max(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    # effective balance will be exactly the same as balance
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_compounding_withdrawal_credentials_over_max(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    # just 1 over the limit, effective balance should be set MAX_EFFECTIVE_BALANCE_ELECTRA during processing
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + 1
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_compounding_withdrawal_credentials_over_max_next_increment(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    # set deposit amount to the next effective balance increment over the limit
    # the validator's effective balance should be set to MAX_EFFECTIVE_BALANCE_ELECTRA
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    # check validator's effective balance
    assert state.validators[validator_index].effective_balance == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_non_versioned_withdrawal_credentials(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        b'\xFF'  # Non specified withdrawal credentials version
        + b'\x02' * 31  # Garabage bytes
    )
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_non_versioned_withdrawal_credentials_over_min_activation(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = (
        b'\xFF'  # Non specified withdrawal credentials version
        + b'\x02' * 31  # Garabage bytes
    )
    # just 1 over the limit, effective balance should be set MIN_ACTIVATION_BALANCE during processing
    amount = spec.MIN_ACTIVATION_BALANCE + 1
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_correct_sig_but_forked_state(spec, state):
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE
    # deposits will always be valid, regardless of the current fork
    state.fork.current_version = spec.Version('0x1234abcd')
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)
    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_incorrect_sig_new_deposit(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount)
    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=False)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_top_up__min_activation_balance(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    state.balances[validator_index] = spec.MIN_ACTIVATION_BALANCE
    state.validators[validator_index].effective_balance = spec.MIN_ACTIVATION_BALANCE

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert state.balances[validator_index] == spec.MIN_ACTIVATION_BALANCE + amount
    assert state.validators[validator_index].effective_balance == spec.MIN_ACTIVATION_BALANCE


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_top_up__min_activation_balance_compounding(spec, state):
    validator_index = 0
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    state.balances[validator_index] = spec.MIN_ACTIVATION_BALANCE
    state.validators[validator_index].withdrawal_credentials = withdrawal_credentials
    state.validators[validator_index].effective_balance = spec.MIN_ACTIVATION_BALANCE

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert state.balances[validator_index] == spec.MIN_ACTIVATION_BALANCE + amount
    assert state.validators[validator_index].effective_balance == spec.MIN_ACTIVATION_BALANCE


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_top_up__max_effective_balance_compounding(spec, state):
    validator_index = 0
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA // 4
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.validators[validator_index].withdrawal_credentials = withdrawal_credentials
    state.validators[validator_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert state.balances[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA + amount
    assert state.validators[validator_index].effective_balance == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_top_up__less_effective_balance(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    initial_balance = spec.MIN_ACTIVATION_BALANCE - 1000
    initial_effective_balance = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] = initial_balance
    state.validators[validator_index].effective_balance = initial_effective_balance

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert state.balances[validator_index] == initial_balance + amount
    # unchanged effective balance
    assert state.validators[validator_index].effective_balance == initial_effective_balance


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_incorrect_sig_top_up(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=False)

    # ensure the deposit signature is incorrect
    assert not spec.is_valid_deposit_signature(
        pending_deposit.pubkey,
        pending_deposit.withdrawal_credentials,
        pending_deposit.amount,
        pending_deposit.signature
    )

    # invalid signatures, in top-ups, are allowed!
    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_incorrect_withdrawal_credentials_top_up(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(b"junk")[1:]
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials
    )

    # inconsistent withdrawal credentials, in top-ups, are allowed!
    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_key_validate_invalid_subgroup(spec, state):
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE

    # All-zero pubkey would not pass `bls.KeyValidate`, but `apply_pending_deposit` would not throw exception
    pubkey = b'\x00' * 48

    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, pubkey=pubkey, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=False)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_key_validate_invalid_decompression(spec, state):
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE

    # `deserialization_fails_infinity_with_true_b_flag` BLS G1 deserialization test case
    # This pubkey would not pass `bls.KeyValidate`, but `apply_pending_deposit` would not throw exception
    pubkey_hex = 'c01000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
    pubkey = bytes.fromhex(pubkey_hex)

    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, pubkey=pubkey, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=False)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_ineffective_deposit_with_bad_fork_version(spec, state):
    validator_index = len(state.validators)
    fork_version = spec.Version('0xAaBbCcDd')
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index=validator_index,
        amount=spec.MIN_ACTIVATION_BALANCE,
        fork_version=fork_version,
        signed=True
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=False)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_with_previous_fork_version(spec, state):
    # Since deposits are valid across forks, the domain is always set with `GENESIS_FORK_VERSION`
    # It's an ineffective deposit because it fails at BLS sig verification
    # NOTE: it was effective in Altair
    assert state.fork.previous_version != state.fork.current_version

    validator_index = len(state.validators)
    fork_version = state.fork.previous_version
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index=validator_index,
        amount=spec.MIN_ACTIVATION_BALANCE,
        fork_version=fork_version,
        signed=True
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=False)


@with_electra_and_later
@spec_state_test
@always_bls
def test_ineffective_deposit_with_current_fork_version(spec, state):
    validator_index = len(state.validators)
    fork_version = state.fork.current_version
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index=validator_index,
        amount=spec.MIN_ACTIVATION_BALANCE,
        fork_version=fork_version,
        signed=True
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=False)


@with_electra_and_later
@spec_state_test
@always_bls
def test_apply_pending_deposit_effective_deposit_with_genesis_fork_version(spec, state):
    assert spec.config.GENESIS_FORK_VERSION not in (state.fork.previous_version, state.fork.current_version)

    validator_index = len(state.validators)
    fork_version = spec.config.GENESIS_FORK_VERSION
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index=validator_index,
        amount=spec.MIN_ACTIVATION_BALANCE,
        fork_version=fork_version,
        signed=True
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_success_top_up_to_withdrawn_validator(spec, state):
    validator_index = 0

    # Fully withdraw validator
    set_validator_fully_withdrawable(spec, state, validator_index)
    assert state.balances[validator_index] > 0
    next_epoch_via_block(spec, state)
    assert state.balances[validator_index] == 0
    assert state.validators[validator_index].effective_balance > 0
    next_epoch_via_block(spec, state)
    assert state.validators[validator_index].effective_balance == 0

    # Make a top-up balance to validator
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    pending_deposit = prepare_pending_deposit(spec, validator_index, amount, signed=True)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert state.balances[validator_index] == amount
    assert state.validators[validator_index].effective_balance == 0

    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    current_epoch = spec.get_current_epoch(state)

    assert spec.is_fully_withdrawable_validator(validator, balance, current_epoch)
