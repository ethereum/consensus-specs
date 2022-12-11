from eth2spec.test.context import (
    spec_configured_state_test,
    spec_state_test_with_matching_config,
    with_all_phases,
    with_phases,
)
from eth2spec.test.helpers.constants import (
    PHASE0, ALTAIR,
    ALL_PHASES,
)
from eth2spec.test.helpers.forks import is_post_fork


@with_phases([ALTAIR])
@spec_configured_state_test({
    'GENESIS_FORK_VERSION': '0x12345678',
    'ALTAIR_FORK_VERSION': '0x11111111',
    'ALTAIR_FORK_EPOCH': 4
})
def test_config_override(spec, state):
    assert spec.config.ALTAIR_FORK_EPOCH == 4
    assert spec.config.GENESIS_FORK_VERSION != spec.Version('0x00000000')
    assert spec.config.GENESIS_FORK_VERSION == spec.Version('0x12345678')
    assert spec.config.ALTAIR_FORK_VERSION == spec.Version('0x11111111')
    assert state.fork.current_version == spec.Version('0x11111111')
    # TODO: it would be nice if the create_genesis_state actually outputs a state
    #  for the fork with a slot that matches at least the fork boundary.
    # assert spec.get_current_epoch(state) >= 4


@with_all_phases
@spec_state_test_with_matching_config
def test_override_config_fork_epoch(spec, state):
    # Fork schedule must be consistent with state fork
    epoch = spec.get_current_epoch(state)
    if is_post_fork(spec.fork, ALTAIR):
        assert state.fork.current_version == spec.compute_fork_version(epoch)
    else:
        assert state.fork.current_version == spec.config.GENESIS_FORK_VERSION

    # Identify state fork
    state_fork = None
    for fork in [fork for fork in ALL_PHASES if is_post_fork(spec.fork, fork)]:
        if fork == PHASE0:
            fork_version_field = 'GENESIS_FORK_VERSION'
        else:
            fork_version_field = fork.upper() + '_FORK_VERSION'
        if state.fork.current_version == getattr(spec.config, fork_version_field):
            state_fork = fork
            break
    assert state_fork is not None

    # Check that all prior forks have already been triggered
    for fork in [fork for fork in ALL_PHASES if is_post_fork(state_fork, fork)]:
        if fork == PHASE0:
            continue
        fork_epoch_field = fork.upper() + '_FORK_EPOCH'
        assert getattr(spec.config, fork_epoch_field) <= epoch
