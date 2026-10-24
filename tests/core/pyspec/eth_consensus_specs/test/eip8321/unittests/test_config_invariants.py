from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8321_and_later,
)
from eth_consensus_specs.test.helpers.keys import pubkeys


@with_eip8321_and_later
@spec_state_test
def test_commitment_registration_delay_hides_activation_epoch_duties(spec, state):
    # Registrants cannot see their activation epoch duties at inclusion
    assert spec.COMMITMENT_REGISTRATION_DELAY >= spec.MIN_SEED_LOOKAHEAD + 2
    assert spec.MAX_RANDAO_COMMITMENT_REGISTRATIONS >= 1


@with_eip8321_and_later
@spec_state_test
def test_new_validator_extends_randao_commitments(spec, state):
    pre_count = len(state.validators)
    assert len(state.randao_commitments) == pre_count

    spec.add_validator_to_registry(
        state,
        pubkeys[pre_count],
        spec.Bytes32(b"\x01" + b"\x00" * 11 + b"\x22" * 20),
        spec.MIN_ACTIVATION_BALANCE,
    )

    assert len(state.validators) == pre_count + 1
    assert len(state.randao_commitments) == pre_count + 1
    assert state.randao_commitments[pre_count] == spec.UNSET_RANDAO_COMMITMENT
