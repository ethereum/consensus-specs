from eth2spec.test.bellatrix.block_processing.test_process_voluntary_exit import (
    run_voluntary_exit_processing_test,
)
from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_deneb_and_later,
)
from eth2spec.test.helpers.constants import (
    DENEB,
)


@with_deneb_and_later
@spec_state_test
@always_bls
def test_invalid_voluntary_exit_with_current_fork_version_not_is_before_fork_epoch(spec, state):
    """
    Since Deneb, the VoluntaryExit domain is fixed to `CAPELLA_FORK_VERSION`
    """
    assert state.fork.current_version != spec.config.CAPELLA_FORK_VERSION
    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=state.fork.current_version,
        is_before_fork_epoch=False,
        valid=False,
    )


@with_deneb_and_later
@spec_state_test
@always_bls
def test_voluntary_exit_with_previous_fork_version_not_is_before_fork_epoch(spec, state):
    """
    Since Deneb, the VoluntaryExit domain is fixed to `CAPELLA_FORK_VERSION`

    Note: This test is valid for ``spec.fork == DENEB`` and invalid for subsequent forks
    """
    assert state.fork.previous_version != state.fork.current_version

    if spec.fork == DENEB:
        assert state.fork.previous_version == spec.config.CAPELLA_FORK_VERSION
        yield from run_voluntary_exit_processing_test(
            spec,
            state,
            fork_version=state.fork.previous_version,
            is_before_fork_epoch=False,
        )
    else:
        assert state.fork.previous_version != spec.config.CAPELLA_FORK_VERSION
        yield from run_voluntary_exit_processing_test(
            spec,
            state,
            fork_version=state.fork.previous_version,
            is_before_fork_epoch=False,
            valid=False,
        )


@with_deneb_and_later
@spec_state_test
@always_bls
def test_voluntary_exit_with_previous_fork_version_is_before_fork_epoch(spec, state):
    """
    Since Deneb, the VoluntaryExit domain is fixed to `CAPELLA_FORK_VERSION`

    Note: This test is valid for ``spec.fork == DENEB`` and invalid for subsequent forks
    """
    assert state.fork.previous_version != state.fork.current_version

    if spec.fork == DENEB:
        assert state.fork.previous_version == spec.config.CAPELLA_FORK_VERSION
        yield from run_voluntary_exit_processing_test(
            spec,
            state,
            fork_version=state.fork.previous_version,
            is_before_fork_epoch=True,
        )
    else:
        assert state.fork.previous_version != spec.config.CAPELLA_FORK_VERSION
        yield from run_voluntary_exit_processing_test(
            spec,
            state,
            fork_version=state.fork.previous_version,
            is_before_fork_epoch=True,
            valid=False,
        )
