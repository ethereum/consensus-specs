from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import HEZE
from eth_consensus_specs.test.helpers.heze.slot_duration import (
    FORK_EPOCH,
    heze_spec_with_slot_duration,
    SLOT_DURATIONS_MS,
)


@with_phases([HEZE])
@spec_test
@single_phase
def test_slot_duration_ms_across_fork(spec):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms)
        assert heze_spec.get_slot_duration_ms(spec.GENESIS_EPOCH) == genesis_ms
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH - 1) == genesis_ms
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH) == slot_duration_ms
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH + 100) == slot_duration_ms


@with_phases([HEZE])
@spec_test
@single_phase
def test_slot_duration_ms_without_scheduled_fork(spec):
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, spec.FAR_FUTURE_EPOCH)
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH + 100) == spec.config.SLOT_DURATION_MS


@with_phases([HEZE])
@spec_test
@single_phase
def test_slot_component_duration_ms(spec):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, duration_ms in [
            (FORK_EPOCH, slot_duration_ms),
            (0, slot_duration_ms),
            (spec.FAR_FUTURE_EPOCH, genesis_ms),
        ]:
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)
            for basis_points in [0, 1, 2500, 3333, 5000, 6667, 7500, spec.BASIS_POINTS]:
                assert (
                    heze_spec.get_slot_component_duration_ms(basis_points)
                    == basis_points * duration_ms // spec.BASIS_POINTS
                )
