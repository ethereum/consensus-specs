from eth2spec.test.context import (
    spec_test,
    with_config_overrides,
    with_matching_spec_config,
    with_phases,
    with_presets,
    with_state,
)
from eth2spec.test.helpers.constants import (
    DENEB, ELECTRA,
    MINIMAL,
)
from eth2spec.test.helpers.light_client_sync import (
    run_lc_sync_test_single_fork,
)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_config_overrides({
    'ELECTRA_FORK_EPOCH': 3,  # Test setup advances to epoch 2
}, emit=False)
@with_state
@with_matching_spec_config(emitted_fork=ELECTRA)
@with_presets([MINIMAL], reason="too slow")
def test_electra_fork(spec, phases, state):
    yield from run_lc_sync_test_single_fork(spec, phases, state, ELECTRA)
