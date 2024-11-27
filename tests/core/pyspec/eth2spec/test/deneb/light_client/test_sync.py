from eth2spec.test.context import (
    spec_test,
    with_config_overrides,
    with_matching_spec_config,
    with_phases,
    with_presets,
    with_state,
)
from eth2spec.test.helpers.constants import (
    ALTAIR, BELLATRIX, CAPELLA, DENEB,
    MINIMAL,
)
from eth2spec.test.helpers.light_client_sync import (
    run_lc_sync_test_multi_fork,
    run_lc_sync_test_single_fork,
    run_lc_sync_test_upgraded_store_with_legacy_data,
)


@with_phases(phases=[CAPELLA], other_phases=[DENEB])
@spec_test
@with_config_overrides({
    'DENEB_FORK_EPOCH': 3,  # Test setup advances to epoch 2
}, emit=False)
@with_state
@with_matching_spec_config(emitted_fork=DENEB)
@with_presets([MINIMAL], reason="too slow")
def test_deneb_fork(spec, phases, state):
    yield from run_lc_sync_test_single_fork(spec, phases, state, DENEB)


@with_phases(phases=[BELLATRIX], other_phases=[CAPELLA, DENEB])
@spec_test
@with_config_overrides({
    'CAPELLA_FORK_EPOCH': 3,  # Test setup advances to epoch 2
    'DENEB_FORK_EPOCH': 4,
}, emit=False)
@with_state
@with_matching_spec_config(emitted_fork=DENEB)
@with_presets([MINIMAL], reason="too slow")
def test_capella_deneb_fork(spec, phases, state):
    yield from run_lc_sync_test_multi_fork(spec, phases, state, CAPELLA, DENEB)


@with_phases(phases=[ALTAIR, BELLATRIX, CAPELLA], other_phases=[CAPELLA, DENEB])
@spec_test
@with_state
@with_matching_spec_config(emitted_fork=DENEB)
@with_presets([MINIMAL], reason="too slow")
def test_deneb_store_with_legacy_data(spec, phases, state):
    yield from run_lc_sync_test_upgraded_store_with_legacy_data(spec, phases, state, DENEB)
