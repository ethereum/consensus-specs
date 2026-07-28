from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_config_overrides,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import EIP8198

FORK_EPOCH = 2


@with_phases([EIP8198])
@spec_test
@with_config_overrides({"EIP8198_FORK_EPOCH": FORK_EPOCH})
@single_phase
def test_gas_limit_transition_at_fork(spec):
    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(FORK_EPOCH))
    parent_gas_limit = spec.Uint64(60_000_000)
    expected_gas_limit = spec.Uint64(
        parent_gas_limit * spec.config.SLOT_DURATION_MS_EIP8198 // spec.config.SLOT_DURATION_MS
    )

    assert spec.is_gas_limit_target_compatible_eip8198(
        parent_gas_limit,
        expected_gas_limit,
        parent_gas_limit,
        spec.Slot(fork_slot - 1),
        fork_slot,
    )
    assert not spec.is_gas_limit_target_compatible_eip8198(
        parent_gas_limit,
        spec.Uint64(expected_gas_limit + 1),
        parent_gas_limit,
        spec.Slot(fork_slot - 1),
        fork_slot,
    )


@with_phases([EIP8198])
@spec_test
@with_config_overrides({"EIP8198_FORK_EPOCH": FORK_EPOCH})
@single_phase
def test_gas_limit_transition_after_missed_slots(spec):
    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(FORK_EPOCH))
    parent_gas_limit = spec.Uint64(60_000_000)
    expected_gas_limit = spec.Uint64(
        parent_gas_limit * spec.config.SLOT_DURATION_MS_EIP8198 // spec.config.SLOT_DURATION_MS
    )

    assert spec.is_gas_limit_target_compatible_eip8198(
        parent_gas_limit,
        expected_gas_limit,
        spec.Uint64(100_000_000),
        spec.Slot(fork_slot - 3),
        spec.Slot(fork_slot + 4),
    )


@with_phases([EIP8198])
@spec_test
@with_config_overrides({"EIP8198_FORK_EPOCH": FORK_EPOCH})
@single_phase
def test_gas_limit_uses_standard_rule_after_transition(spec):
    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(FORK_EPOCH))
    parent_gas_limit = spec.Uint64(40_000_000)
    target_gas_limit = spec.Uint64(60_000_000)
    max_difference = max(parent_gas_limit // 1024, 1) - 1
    expected_gas_limit = spec.Uint64(parent_gas_limit + max_difference)

    assert spec.is_gas_limit_target_compatible_eip8198(
        parent_gas_limit,
        expected_gas_limit,
        target_gas_limit,
        fork_slot,
        spec.Slot(fork_slot + 1),
    )
    assert spec.is_gas_limit_target_compatible(
        parent_gas_limit, expected_gas_limit, target_gas_limit
    )
