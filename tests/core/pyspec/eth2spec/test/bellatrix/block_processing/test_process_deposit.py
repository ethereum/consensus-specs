from eth2spec.test.context import (
    spec_state_test,
    always_bls,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.deposits import (
    run_deposit_processing_with_specific_fork_version,
)


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_ineffective_deposit_with_previous_fork_version(spec, state):
    # Since deposits are valid across forks, the domain is always set with `GENESIS_FORK_VERSION`.
    # It's an ineffective deposit because it fails at BLS sig verification.
    # NOTE: it was effective in Altair.
    assert state.fork.previous_version != state.fork.current_version

    yield from run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=state.fork.previous_version,
        effective=False,
    )


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_effective_deposit_with_genesis_fork_version(spec, state):
    assert spec.config.GENESIS_FORK_VERSION not in (
        state.fork.previous_version,
        state.fork.current_version,
    )

    yield from run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=spec.config.GENESIS_FORK_VERSION,
    )
