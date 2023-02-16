from eth2spec.test.helpers.keys import pubkeys, privkeys, pubkey_to_privkey
from eth2spec.test.helpers.pubkey_changes import get_signed_pubkey_change

from eth2spec.test.context import spec_state_test, expect_assertion_error, with_revoke_and_later, always_bls

def run_pubkey_change_processing(spec, state, signed_pubkey_change, valid=True):
    """
    Run ``process_pubkey_change``, yielding:
      - pre-state ('pre')
      - pubkey-change ('pubkey_change')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state - this will store some values to check later that certain updates happended.
    yield 'pre', state

    yield 'pubkey_change', signed_pubkey_change

    # If the pubkey_change is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_pubkey_change(state, signed_pubkey_change))
        yield 'post', None
        return

    # process pubkey change
    spec.process_pubkey_change(state, signed_pubkey_change)

    # Make sure the address change has been processed
    validator_index = signed_pubkey_change.message.validator_index
    validator = state.validators[validator_index]
    
    assert validator.new_pubkey == signed_pubkey_change.message.new_pubkey
    assert validator.pubkey_change_epoch == signed_pubkey_change.message.epoch  

    # yield post-state
    yield 'post', state


##### The below are the test cases for bls to execution change processing

@with_revoke_and_later
@spec_state_test
def test_success(spec, state):
    signed_pubkey_change = get_signed_pubkey_change(spec, state)
    yield from run_pubkey_change_processing(spec, state, signed_pubkey_change)

"""
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
    assert not spec.is_fully_withdrawable_validator(validator, balance, spec.get_current_epoch(state))


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
    assert not spec.is_fully_withdrawable_validator(validator, balance, spec.get_current_epoch(state))


@with_capella_and_later
@spec_state_test
def test_success_in_exit_queue(spec, state):
    validator_index = 3
    spec.initiate_validator_exit(state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))
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
    assert not spec.is_fully_withdrawable_validator(validator, balance, spec.get_current_epoch(state))


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
def test_fail_val_index_out_of_range(spec, state):
    # Create for one validator beyond the validator list length
    signed_address_change = get_signed_address_change(spec, state, validator_index=len(state.validators))

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_already_0x01(spec, state):
    # Create for one validator beyond the validator list length
    validator_index = len(state.validators) // 2
    validator = state.validators[validator_index]
    validator.withdrawal_credentials = b'\x01' + b'\x00' * 11 + b'\x23' * 20
    signed_address_change = get_signed_address_change(spec, state, validator_index=validator_index)

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_from_bls_pubkey(spec, state):
    # Create for one validator beyond the validator list length
    validator_index = 2
    signed_address_change = get_signed_address_change(
        spec, state,
        validator_index=validator_index,
        withdrawal_pubkey=pubkeys[0],
    )

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change, valid=False)


@with_capella_and_later
@spec_state_test
@always_bls
def test_fail_bad_signature(spec, state):
    signed_address_change = get_signed_address_change(spec, state)
    # Mutate signature
    signed_address_change.signature = spec.BLSSignature(b'\x42' * 96)

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change, valid=False)
"""
