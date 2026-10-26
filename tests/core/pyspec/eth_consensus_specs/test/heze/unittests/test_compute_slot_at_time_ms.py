from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_config_overrides,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import HEZE


@with_phases([HEZE])
@spec_test
@with_config_overrides({"HEZE_FORK_EPOCH": 2, "SLOT_DURATION_MS_HEZE": 10000})
@single_phase
def test_compute_slot_at_time_ms_at_heze_fork(spec):
    genesis_time_ms = 1_000_000
    fork_slot = spec.compute_start_slot_at_epoch(spec.config.HEZE_FORK_EPOCH)
    fork_time_ms = genesis_time_ms + fork_slot * spec.config.SLOT_DURATION_MS

    for time_ms, expected_slot in (
        (genesis_time_ms, spec.GENESIS_SLOT),
        (genesis_time_ms + spec.config.SLOT_DURATION_MS - 1, spec.GENESIS_SLOT),
        (fork_time_ms - spec.config.SLOT_DURATION_MS, fork_slot - 1),
        (fork_time_ms - 1, fork_slot - 1),
        (fork_time_ms, fork_slot),
        (fork_time_ms + spec.config.SLOT_DURATION_MS_HEZE - 1, fork_slot),
        (fork_time_ms + spec.config.SLOT_DURATION_MS_HEZE, fork_slot + 1),
        (
            fork_time_ms + spec.SLOTS_PER_EPOCH * spec.config.SLOT_DURATION_MS_HEZE,
            fork_slot + spec.SLOTS_PER_EPOCH,
        ),
    ):
        assert spec.compute_slot_at_time_ms(genesis_time_ms, time_ms) == expected_slot
