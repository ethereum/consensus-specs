from eth2spec.test.context import (
    spec_test,
    with_config_overrides,
    with_matching_spec_config,
    with_phases,
    with_presets,
    with_state,
)
from eth2spec.test.helpers.constants import (
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    MINIMAL,
)
from eth2spec.test.helpers.light_client_sync import (
    run_lc_sync_test_multi_fork,
    run_lc_sync_test_single_fork,
)


@with_phases(phases=[BELLATRIX], other_phases=[CAPELLA])
@spec_test
@with_config_overrides(
    {
        "CAPELLA_FORK_EPOCH": 3,  # Test setup advances to epoch 2
    },
)
@with_state
@with_matching_spec_config(emitted_fork=CAPELLA)
@with_presets([MINIMAL], reason="too slow")
def test_capella_fork(spec, phases, state):
    yield from run_lc_sync_test_single_fork(spec, phases, state, CAPELLA)


@with_phases(phases=[BELLATRIX], other_phases=[CAPELLA, DENEB])
@spec_test
@with_config_overrides(
    {
        "CAPELLA_FORK_EPOCH": 3,  # Test setup advances to epoch 2
        "DENEB_FORK_EPOCH": 4,
    },
)
@with_state
@with_matching_spec_config(emitted_fork=DENEB)
@with_presets([MINIMAL], reason="too slow")
def test_capella_deneb_fork(spec, phases, state):
    yield from run_lc_sync_test_multi_fork(spec, phases, state, CAPELLA, DENEB)


@with_phases(phases=[BELLATRIX], other_phases=[CAPELLA, DENEB, ELECTRA])
@spec_test
@with_config_overrides(
    {
        "CAPELLA_FORK_EPOCH": 3,  # Test setup advances to epoch 2
        "DENEB_FORK_EPOCH": 4,
        "ELECTRA_FORK_EPOCH": 5,
    },
)
@with_state
@with_matching_spec_config(emitted_fork=ELECTRA)
@with_presets([MINIMAL], reason="too slow")
def test_capella_electra_fork(spec, phases, state):
    yield from run_lc_sync_test_multi_fork(spec, phases, state, CAPELLA, ELECTRA)
