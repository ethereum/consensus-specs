from eth2spec.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_capella_and_later,
    with_phases,
    with_presets,
)
from eth2spec.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth2spec.test.helpers.constants import CAPELLA, MAINNET
from eth2spec.test.helpers.keys import pubkeys


def run_bls_to_execution_change_processing(spec, state, signed_address_change, valid=True):
    """
    Run ``process_bls_to_execution_change``, yielding:
      - pre-state ('pre')
      - address-change ('address_change')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield "pre", state

    yield "address_change", signed_address_change

    # If the address_change is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(
            lambda: spec.process_bls_to_execution_change(state, signed_address_change)
        )
        yield "post", None
        return

    # process address change
    spec.process_bls_to_execution_change(state, signed_address_change)

    # Make sure the address change has been processed
    validator_index = signed_address_change.message.validator_index
    validator = state.validators[validator_index]
    assert validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert validator.withdrawal_credentials[1:12] == b"\x00" * 11
    assert (
        validator.withdrawal_credentials[12:] == signed_address_change.message.to_execution_address
    )

    # yield post-state
    yield "post", state


@with_capella_and_later
@spec_state_test
def test_success(spec, state):
    signed_address_change = get_signed_address_change(spec, state)
    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)


@with_capella_and_later
@spec_state_test
def test_success_not_activated(spec, state):
    validator_index = 3
    validator = state.validators[validator_index]
    validator.activation_eligibility_epoch += 4
    validator.activation_epoch = spec.FAR_FUTURE_EPOCH

    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    signed_address_change = get_signed_address_change(spec, state)
    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)

    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    assert not spec.is_fully_withdrawable_validator(
        validator, balance, spec.get_current_epoch(state)
    )


@with_capella_and_later
@spec_state_test
def test_success_in_activation_queue(spec, state):
    validator_index = 3
    validator = state.validators[validator_index]
    validator.activation_eligibility_epoch = spec.get_current_epoch(state)
    validator.activation_epoch += 4

    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    signed_address_change = get_signed_address_change(spec, state)
    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)

    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    assert not spec.is_fully_withdrawable_validator(
        validator, balance, spec.get_current_epoch(state)
    )


@with_capella_and_later
@spec_state_test
def test_success_in_exit_queue(spec, state):
    validator_index = 3
    spec.initiate_validator_exit(state, validator_index)

    assert spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )
    assert spec.get_current_epoch(state) < state.validators[validator_index].exit_epoch

    signed_address_change = get_signed_address_change(spec, state, validator_index=validator_index)
    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)


@with_capella_and_later
@spec_state_test
def test_success_exited(spec, state):
    validator_index = 4
    validator = state.validators[validator_index]
    validator.exit_epoch = spec.get_current_epoch(state)

    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    signed_address_change = get_signed_address_change(spec, state, validator_index=validator_index)
    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)

    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    assert not spec.is_fully_withdrawable_validator(
        validator, balance, spec.get_current_epoch(state)
    )


@with_capella_and_later
@spec_state_test
def test_success_withdrawable(spec, state):
    validator_index = 4
    validator = state.validators[validator_index]
    validator.exit_epoch = spec.get_current_epoch(state)
    validator.withdrawable_epoch = spec.get_current_epoch(state)

    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    signed_address_change = get_signed_address_change(spec, state, validator_index=validator_index)
    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)

    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    assert spec.is_fully_withdrawable_validator(validator, balance, spec.get_current_epoch(state))


@with_capella_and_later
@spec_state_test
def test_invalid_val_index_out_of_range(spec, state):
    # Create for one validator beyond the validator list length
    signed_address_change = get_signed_address_change(
        spec, state, validator_index=len(state.validators)
    )

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_capella_and_later
@spec_state_test
def test_invalid_already_0x01(spec, state):
    # Create for one validator beyond the validator list length
    validator_index = len(state.validators) // 2
    validator = state.validators[validator_index]
    validator.withdrawal_credentials = b"\x01" + b"\x00" * 11 + b"\x23" * 20
    signed_address_change = get_signed_address_change(spec, state, validator_index=validator_index)

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_capella_and_later
@spec_state_test
def test_invalid_incorrect_from_bls_pubkey(spec, state):
    # Create for one validator beyond the validator list length
    validator_index = 2
    signed_address_change = get_signed_address_change(
        spec,
        state,
        validator_index=validator_index,
        withdrawal_pubkey=pubkeys[0],
    )

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_capella_and_later
@spec_state_test
@always_bls
def test_invalid_bad_signature(spec, state):
    signed_address_change = get_signed_address_change(spec, state)
    # Mutate signature
    signed_address_change.signature = spec.BLSSignature(b"\x42" * 96)

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_capella_and_later
@spec_state_test
@always_bls
def test_genesis_fork_version(spec, state):
    signed_address_change = get_signed_address_change(
        spec, state, fork_version=spec.config.GENESIS_FORK_VERSION
    )

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)


@with_capella_and_later
@spec_state_test
@always_bls
def test_invalid_current_fork_version(spec, state):
    signed_address_change = get_signed_address_change(
        spec, state, fork_version=state.fork.current_version
    )

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_capella_and_later
@spec_state_test
@always_bls
def test_invalid_previous_fork_version(spec, state):
    signed_address_change = get_signed_address_change(
        spec, state, fork_version=state.fork.previous_version
    )

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_capella_and_later
@spec_state_test
@always_bls
def test_invalid_genesis_validators_root(spec, state):
    signed_address_change = get_signed_address_change(
        spec, state, genesis_validators_root=b"\x99" * 32
    )

    yield from run_bls_to_execution_change_processing(
        spec, state, signed_address_change, valid=False
    )


@with_phases([CAPELLA])
@with_presets([MAINNET], reason="use mainnet fork version")
@spec_state_test
@always_bls
def test_valid_signature_from_staking_deposit_cli(spec, state):
    validator_index = 1
    from_bls_pubkey = bytes.fromhex(
        "86248e64705987236ec3c41f6a81d96f98e7b85e842a1d71405b216fa75a9917512f3c94c85779a9729c927ea2aa9ed1"
    )  # noqa: E501
    to_execution_address = bytes.fromhex("3434343434343434343434343434343434343434")
    signature = bytes.fromhex(
        "8cf4219884b326a04f6664b680cd9a99ad70b5280745af1147477aa9f8b4a2b2b38b8688c6a74a06f275ad4e14c5c0c70e2ed37a15ece5bf7c0724a376ad4c03c79e14dd9f633a3d54abc1ce4e73bec3524a789ab9a69d4d06686a8a67c9e4dc"
    )  # noqa: E501

    # Use mainnet `genesis_validators_root`
    state.genesis_validators_root = bytes.fromhex(
        "4b363db94e286120d76eb905340fdd4e54bfe9f06bf33ff6cf5ad27f511bfe95"
    )
    validator = state.validators[validator_index]
    validator.withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(from_bls_pubkey)[1:]

    address_change = spec.BLSToExecutionChange(
        validator_index=validator_index,
        from_bls_pubkey=from_bls_pubkey,
        to_execution_address=to_execution_address,
    )
    signed_address_change = spec.SignedBLSToExecutionChange(
        message=address_change,
        signature=signature,
    )

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)
