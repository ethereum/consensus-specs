from eth_consensus_specs.test.context import (
    spec_test,
    with_config_overrides,
    with_matching_spec_config,
    with_phases,
    with_presets,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    FULU,
    GLOAS,
    MINIMAL,
)
from eth_consensus_specs.test.helpers.light_client_sync import (
    run_lc_sync_test_single_fork,
)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_config_overrides(
    {
        "GLOAS_FORK_EPOCH": 3,  # Test setup advances to epoch 2
    },
)
@with_state
@with_matching_spec_config(emitted_fork=GLOAS)
@with_presets([MINIMAL], reason="too slow")
def test_gloas_fork(spec, phases, state):
    yield from run_lc_sync_test_single_fork(spec, phases, state, GLOAS)
