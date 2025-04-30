from eth2spec.test.context import (
    with_phases,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.state import transition_to
from eth2spec.test.helpers.attestations import (
    run_attestation_processing,
    get_valid_attestation,
)
from eth2spec.test.helpers.typing import SpecForkName

CUSTODY_GAME = SpecForkName("custody_game")


@with_phases([CUSTODY_GAME])
@spec_state_test
@always_bls
def test_on_time_success(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_phases([CUSTODY_GAME])
@spec_state_test
@always_bls
def test_late_success(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY + 1)

    yield from run_attestation_processing(spec, state, attestation)
