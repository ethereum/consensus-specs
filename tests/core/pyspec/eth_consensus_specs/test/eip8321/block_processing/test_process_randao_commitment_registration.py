from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8321_and_later,
)
from eth_consensus_specs.test.helpers.eip8321.randao import (
    activate_commitment,
    get_commitment,
    get_signed_registration,
)
from eth_consensus_specs.test.helpers.keys import privkeys


def run_randao_commitment_registration_processing(spec, state, signed_registration, valid=True):
    """
    Run ``process_randao_commitment_registration``, yielding:
      - pre-state ('pre')
      - registration ('randao_commitment_registration')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state

    yield "randao_commitment_registration", signed_registration

    # If the registration is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(
            lambda: spec.process_randao_commitment_registration(state, signed_registration)
        )
        yield "post", None
        return

    pending_count = len(state.pending_randao_commitments)
    spec.process_randao_commitment_registration(state, signed_registration)

    # The registration is queued, not applied: the validator stays on the legacy path
    registration = signed_registration.message
    assert state.randao_commitments[registration.validator_index] == spec.Bytes32()
    assert len(state.pending_randao_commitments) == pending_count + 1

    pending = state.pending_randao_commitments[pending_count]
    assert pending.validator_index == registration.validator_index
    assert pending.commitment == registration.commitment
    assert pending.activation_epoch == (
        spec.get_current_epoch(state) + spec.COMMITMENT_REGISTRATION_DELAY
    )

    yield "post", state


@with_eip8321_and_later
@spec_state_test
def test_success(spec, state):
    signed_registration = get_signed_registration(spec, state)
    yield from run_randao_commitment_registration_processing(spec, state, signed_registration)


@with_eip8321_and_later
@spec_state_test
def test_success_last_validator(spec, state):
    validator_index = len(state.validators) - 1
    signed_registration = get_signed_registration(spec, state, validator_index=validator_index)
    yield from run_randao_commitment_registration_processing(spec, state, signed_registration)


@with_eip8321_and_later
@spec_state_test
def test_success_exited_validator(spec, state):
    # Registration is independent of a validator's status in the registry
    validator_index = 3
    spec.initiate_validator_exit(state, validator_index)

    signed_registration = get_signed_registration(spec, state, validator_index=validator_index)
    yield from run_randao_commitment_registration_processing(spec, state, signed_registration)


@with_eip8321_and_later
@spec_state_test
def test_success_second_validator_with_one_pending(spec, state):
    # The one-pending rule is per validator, not global
    first = get_signed_registration(spec, state, validator_index=0)
    spec.process_randao_commitment_registration(state, first)

    signed_registration = get_signed_registration(spec, state, validator_index=1)
    yield from run_randao_commitment_registration_processing(spec, state, signed_registration)


@with_eip8321_and_later
@spec_state_test
def test_invalid_validator_index_out_of_range(spec, state):
    validator_index = len(state.validators)
    signed_registration = get_signed_registration(spec, state, validator_index=validator_index)
    yield from run_randao_commitment_registration_processing(
        spec, state, signed_registration, valid=False
    )


@with_eip8321_and_later
@spec_state_test
def test_invalid_zero_commitment(spec, state):
    signed_registration = get_signed_registration(spec, state, commitment=spec.Bytes32())
    yield from run_randao_commitment_registration_processing(
        spec, state, signed_registration, valid=False
    )


@with_eip8321_and_later
@spec_state_test
def test_invalid_already_registered(spec, state):
    validator_index = 0
    activate_commitment(spec, state, validator_index)

    signed_registration = get_signed_registration(spec, state, validator_index=validator_index)
    yield from run_randao_commitment_registration_processing(
        spec, state, signed_registration, valid=False
    )


@with_eip8321_and_later
@spec_state_test
def test_invalid_registration_already_pending(spec, state):
    validator_index = 0
    signed_registration = get_signed_registration(spec, state, validator_index=validator_index)
    spec.process_randao_commitment_registration(state, signed_registration)

    # A second registration for the same validator is rejected while the first is in flight,
    # even with a different commitment
    other = get_signed_registration(
        spec,
        state,
        validator_index=validator_index,
        commitment=get_commitment(spec, validator_index + 1),
    )
    yield from run_randao_commitment_registration_processing(spec, state, other, valid=False)


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_invalid_incorrect_signature(spec, state):
    validator_index = 0
    signed_registration = get_signed_registration(
        spec, state, validator_index=validator_index, privkey=privkeys[validator_index + 1]
    )
    yield from run_randao_commitment_registration_processing(
        spec, state, signed_registration, valid=False
    )


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_invalid_signature_over_different_commitment(spec, state):
    validator_index = 0
    signed_registration = get_signed_registration(spec, state, validator_index=validator_index)
    signed_registration.message.commitment = get_commitment(spec, validator_index + 1)
    yield from run_randao_commitment_registration_processing(
        spec, state, signed_registration, valid=False
    )
