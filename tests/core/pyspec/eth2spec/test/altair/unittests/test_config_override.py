from eth2spec.test.context import (
    spec_configured_state_test,
    spec_state_test_with_matching_config,
    with_all_phases,
    with_phases,
)
from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.test.helpers.forks import (
    is_post_capella, is_post_eip4844,
)


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
    if state.fork.current_version == spec.config.GENESIS_FORK_VERSION:
        return

    assert spec.config.ALTAIR_FORK_EPOCH == spec.GENESIS_EPOCH
    if state.fork.current_version == spec.config.ALTAIR_FORK_VERSION:
        return

    assert spec.config.BELLATRIX_FORK_EPOCH == spec.GENESIS_EPOCH
    if state.fork.current_version == spec.config.BELLATRIX_FORK_VERSION:
        return

    if is_post_capella(spec):
        assert spec.config.CAPELLA_FORK_EPOCH == spec.GENESIS_EPOCH
        if state.fork.current_version == spec.config.CAPELLA_FORK_VERSION:
            return

    if is_post_eip4844(spec):
        assert spec.config.EIP4844_FORK_EPOCH == spec.GENESIS_EPOCH
        if state.fork.current_version == spec.config.EIP4844_FORK_VERSION:
            return

    assert spec.config.SHARDING_FORK_EPOCH == spec.GENESIS_EPOCH
    if state.fork.current_version == spec.config.SHARDING_FORK_VERSION:
        return

    assert False  # Fork is missing
