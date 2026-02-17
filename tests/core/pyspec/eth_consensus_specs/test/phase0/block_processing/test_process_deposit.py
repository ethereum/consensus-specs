from eth_consensus_specs.test.context import always_bls, spec_state_test, with_all_phases
from eth_consensus_specs.test.helpers.deposits import (
    build_deposit,
    prepare_state_and_deposit,
    run_deposit_processing,
    run_deposit_processing_with_specific_fork_version,
    sign_deposit_data,
)
from eth_consensus_specs.test.helpers.forks import is_post_electra
from eth_consensus_specs.test.helpers.keys import privkeys, pubkeys


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
        + b"\x00" * 11  # specified 0s
        + b"\x59" * 20  # a 20-byte eth1 address
    )
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(
        spec,
        state,
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
        b"\xff" + b"\x02" * 31  # Non specified withdrawal credentials version  # Garbage bytes
    )
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(
        spec,
        state,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
@always_bls
def test_correct_sig_but_forked_state(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    # deposits will always be valid, regardless of the current fork
    state.fork.current_version = spec.Version("0x1234abcd")
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)
    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
@always_bls
def test_incorrect_sig_new_deposit(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)
    yield from run_deposit_processing(spec, state, deposit, validator_index, effective=False)


@with_all_phases
@spec_state_test
def test_top_up__max_effective_balance(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE
    state.validators[validator_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE

    yield from run_deposit_processing(spec, state, deposit, validator_index)

    if not is_post_electra(spec):
        assert state.balances[validator_index] == spec.MAX_EFFECTIVE_BALANCE + amount
        assert state.validators[validator_index].effective_balance == spec.MAX_EFFECTIVE_BALANCE


@with_all_phases
@spec_state_test
def test_top_up__less_effective_balance(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    initial_balance = spec.MAX_EFFECTIVE_BALANCE - 1000
    initial_effective_balance = spec.MAX_EFFECTIVE_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] = initial_balance
    state.validators[validator_index].effective_balance = initial_effective_balance

    yield from run_deposit_processing(spec, state, deposit, validator_index)

    if not is_post_electra(spec):
        assert state.balances[validator_index] == initial_balance + amount
        # unchanged effective balance
        assert state.validators[validator_index].effective_balance == initial_effective_balance


@with_all_phases
@spec_state_test
def test_top_up__zero_balance(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    initial_balance = 0
    initial_effective_balance = 0
    state.balances[validator_index] = initial_balance
    state.validators[validator_index].effective_balance = initial_effective_balance

    yield from run_deposit_processing(spec, state, deposit, validator_index)

    if not is_post_electra(spec):
        assert state.balances[validator_index] == initial_balance + amount
        # unchanged effective balance
        assert state.validators[validator_index].effective_balance == initial_effective_balance


@with_all_phases
@spec_state_test
@always_bls
def test_incorrect_sig_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)

    # invalid signatures, in top-ups, are allowed!
    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_incorrect_withdrawal_credentials_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(b"junk")[1:]
    deposit = prepare_state_and_deposit(
        spec, state, validator_index, amount, withdrawal_credentials=withdrawal_credentials
    )

    # inconsistent withdrawal credentials, in top-ups, are allowed!
    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_invalid_wrong_deposit_for_deposit_count(spec, state):
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
        withdrawal_credentials=b"\x00" * 32,
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
        withdrawal_credentials=b"\x00" * 32,
        signed=True,
    )

    # state has root for deposit_2 but is at deposit_count for deposit_1
    state.eth1_data.deposit_root = root_2
    state.eth1_data.deposit_count = deposit_count_1

    yield from run_deposit_processing(spec, state, deposit_2, index_2, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_bad_merkle_proof(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)

    # mess up merkle branch
    deposit.proof[5] = spec.Bytes32()

    sign_deposit_data(spec, deposit.data, privkeys[validator_index])

    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=False)


@with_all_phases
@spec_state_test
def test_key_validate_invalid_subgroup(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE

    # All-zero pubkey would not pass `bls.KeyValidate`, but `process_deposit` would not throw exception.
    pubkey = b"\x00" * 48

    deposit = prepare_state_and_deposit(
        spec, state, validator_index, amount, pubkey=pubkey, signed=True
    )

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
def test_key_validate_invalid_decompression(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE

    # `deserialization_fails_infinity_with_true_b_flag` BLS G1 deserialization test case.
    # This pubkey would not pass `bls.KeyValidate`, but `process_deposit` would not throw exception.
    pubkey_hex = "c01000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    pubkey = bytes.fromhex(pubkey_hex)

    deposit = prepare_state_and_deposit(
        spec, state, validator_index, amount, pubkey=pubkey, signed=True
    )

    yield from run_deposit_processing(spec, state, deposit, validator_index)


@with_all_phases
@spec_state_test
@always_bls
def test_ineffective_deposit_with_bad_fork_version(spec, state):
    yield from run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=spec.Version("0xAaBbCcDd"),
        effective=False,
    )
