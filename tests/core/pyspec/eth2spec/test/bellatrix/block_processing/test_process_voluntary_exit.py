from eth2spec.test.context import (
    spec_state_test,
    always_bls,
    with_bellatrix_and_later,
    with_phases,
)
from eth2spec.test.helpers.constants import (
    BELLATRIX,
    CAPELLA,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.state import (
    next_epoch,
)
from eth2spec.test.helpers.voluntary_exits import (
    run_voluntary_exit_processing,
    sign_voluntary_exit,
)

BELLATRIX_AND_CAPELLA = [BELLATRIX, CAPELLA]


def run_voluntary_exit_processing_test(
    spec, state, fork_version, is_before_fork_epoch, valid=True
):
    # create a fork
    next_epoch(spec, state)
    state.fork.epoch = spec.get_current_epoch(state)

    voluntary_exit_epoch = 0 if is_before_fork_epoch else state.fork.epoch

    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = spec.VoluntaryExit(
        epoch=voluntary_exit_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        voluntary_exit,
        privkey,
        fork_version=fork_version,
    )

    yield from run_voluntary_exit_processing(
        spec, state, signed_voluntary_exit, valid=valid
    )


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_invalid_voluntary_exit_with_current_fork_version_is_before_fork_epoch(
    spec, state
):
    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=state.fork.current_version,
        is_before_fork_epoch=True,
        valid=False,
    )


@with_phases(BELLATRIX_AND_CAPELLA)
@spec_state_test
@always_bls
def test_voluntary_exit_with_current_fork_version_not_is_before_fork_epoch(spec, state):
    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=state.fork.current_version,
        is_before_fork_epoch=False,
    )


@with_phases([BELLATRIX, CAPELLA])
@spec_state_test
@always_bls
def test_voluntary_exit_with_previous_fork_version_is_before_fork_epoch(spec, state):
    assert state.fork.previous_version != state.fork.current_version

    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=state.fork.previous_version,
        is_before_fork_epoch=True,
    )


@with_phases(BELLATRIX_AND_CAPELLA)
@spec_state_test
@always_bls
def test_invalid_voluntary_exit_with_previous_fork_version_not_is_before_fork_epoch(
    spec, state
):
    assert state.fork.previous_version != state.fork.current_version

    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=state.fork.previous_version,
        is_before_fork_epoch=False,
        valid=False,
    )


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_invalid_voluntary_exit_with_genesis_fork_version_is_before_fork_epoch(
    spec, state
):
    assert spec.config.GENESIS_FORK_VERSION not in (
        state.fork.previous_version,
        state.fork.current_version,
    )

    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=spec.config.GENESIS_FORK_VERSION,
        is_before_fork_epoch=True,
        valid=False,
    )


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_invalid_voluntary_exit_with_genesis_fork_version_not_is_before_fork_epoch(
    spec, state
):
    assert spec.config.GENESIS_FORK_VERSION not in (
        state.fork.previous_version,
        state.fork.current_version,
    )

    yield from run_voluntary_exit_processing_test(
        spec,
        state,
        fork_version=spec.config.GENESIS_FORK_VERSION,
        is_before_fork_epoch=False,
        valid=False,
    )
