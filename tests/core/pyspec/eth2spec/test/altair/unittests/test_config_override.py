from eth2spec.test.context import spec_configured_state_test, with_phases
from eth2spec.test.helpers.constants import ALTAIR


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
