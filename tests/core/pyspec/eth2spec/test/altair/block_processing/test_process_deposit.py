from eth2spec.test.context import (
    spec_state_test,
    always_bls,
    with_altair_and_later,
    with_phases,
)
from eth2spec.test.helpers.constants import (
    ALTAIR,
)


from eth2spec.test.helpers.deposits import (
    run_deposit_processing_with_specific_fork_version,
)


@with_phases([ALTAIR])
@spec_state_test
@always_bls
def test_effective_deposit_with_previous_fork_version(spec, state):
    assert state.fork.previous_version != state.fork.current_version

    yield from run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=state.fork.previous_version,
        effective=True,
    )


@with_altair_and_later
@spec_state_test
@always_bls
def test_ineffective_deposit_with_bad_fork_version_and(spec, state):
    yield from run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=spec.Version('0xAaBbCcDd'),
        effective=False,
    )
