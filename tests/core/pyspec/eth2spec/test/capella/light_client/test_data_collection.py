from eth2spec.test.context import (
    spec_test,
    with_config_overrides,
    with_matching_spec_config,
    with_phases,
    with_presets,
    with_state,
)
from eth2spec.test.helpers.constants import (
    CAPELLA,
    DENEB,
    ELECTRA,
    MINIMAL,
)
from eth2spec.test.helpers.light_client_data_collection import (
    run_lc_data_collection_test_multi_fork,
)


@with_phases(phases=[CAPELLA], other_phases=[DENEB, ELECTRA])
@spec_test
@with_config_overrides(
    {
        "DENEB_FORK_EPOCH": 1 * 8,  # SyncCommitteePeriod 1
        "ELECTRA_FORK_EPOCH": 2 * 8,  # SyncCommitteePeriod 2
    },
    emit=False,
)
@with_state
@with_matching_spec_config(emitted_fork=ELECTRA)
@with_presets([MINIMAL], reason="too slow")
def test_deneb_electra_reorg_aligned(spec, phases, state):
    yield from run_lc_data_collection_test_multi_fork(
        spec, phases, state, DENEB, ELECTRA
    )


@with_phases(phases=[CAPELLA], other_phases=[DENEB, ELECTRA])
@spec_test
@with_config_overrides(
    {
        "DENEB_FORK_EPOCH": 1 * 8 + 4,  # SyncCommitteePeriod 1 (+ 4 epochs)
        "ELECTRA_FORK_EPOCH": 3 * 8 + 4,  # SyncCommitteePeriod 3 (+ 4 epochs)
    },
    emit=False,
)
@with_state
@with_matching_spec_config(emitted_fork=ELECTRA)
@with_presets([MINIMAL], reason="too slow")
def test_deneb_electra_reorg_unaligned(spec, phases, state):
    yield from run_lc_data_collection_test_multi_fork(
        spec, phases, state, DENEB, ELECTRA
    )
