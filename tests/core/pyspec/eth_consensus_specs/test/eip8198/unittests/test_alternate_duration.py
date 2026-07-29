"""
Spot-check that derived EIP-8198 values follow the slot duration schedule for
a range of alternate durations, so no rule hard-codes a particular ratio.
Slot boundary times must stay exact integer seconds for every duration.
"""

from frozendict import frozendict

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL

FORK_EPOCH = 4096


def _alternate_config(duration_ms):
    return {
        "EIP8198_FORK_EPOCH": FORK_EPOCH,
        "SLOT_DURATION_SCHEDULE": (
            frozendict({"EPOCH": FORK_EPOCH, "SLOT_DURATION_MS": duration_ms}),
        ),
    }


def run_alternate_duration_checks(spec, state):
    pre_ms = spec.config.SLOT_DURATION_MS
    post_ms = spec.get_slot_duration_ms(spec.Epoch(FORK_EPOCH))
    assert post_ms != pre_ms

    # Piecewise timeline, exact at integer-second slot boundaries
    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(FORK_EPOCH))
    fork_time_ms = spec.compute_slot_start_time_ms(state.genesis_time, fork_slot)
    next_slot_time_ms = fork_time_ms + post_ms
    assert spec.compute_slot_start_time_ms(state.genesis_time, spec.Slot(fork_slot + 1)) == (
        next_slot_time_ms
    )
    assert (
        spec.compute_slot_at_time_ms(state.genesis_time, spec.Uint64(next_slot_time_ms - 1))
        == fork_slot
    )
    assert spec.compute_slot_at_time_ms(state.genesis_time, next_slot_time_ms) == fork_slot + 1
    for slot in (fork_slot - 1, fork_slot, spec.Slot(fork_slot + 100)):
        start_ms = spec.compute_slot_start_time_ms(state.genesis_time, slot)
        assert start_ms % 1000 == 0
        assert spec.compute_time_at_slot(state, slot) * 1000 == (
            spec.compute_time_at_slot_ms(state, slot)
        )

    # Intra-slot deadlines
    assert spec.get_attestation_due_ms(fork_slot) == (
        spec.config.ATTESTATION_DUE_BPS_GLOAS * post_ms // spec.BASIS_POINTS
    )

    # Issuance and churn
    assert spec.get_base_reward_per_increment(state) == (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * spec.get_slot_duration_ms(spec.get_current_epoch(state))
        // pre_ms
        // spec.integer_squareroot(spec.get_total_active_balance(state))
    )
    raw_exit = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        spec.get_total_active_balance(state) // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    expected_exit = raw_exit * spec.get_slot_duration_ms(spec.get_current_epoch(state)) // pre_ms
    expected_exit -= expected_exit % spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.get_exit_churn_limit(state) == expected_exit

    # Retention window preserves its wall-clock length after the change
    window_epochs = spec.config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    window_ms = window_epochs * spec.SLOTS_PER_EPOCH * pre_ms
    current_epoch = spec.Epoch(FORK_EPOCH + window_epochs)
    start_epoch = spec.get_data_column_sidecars_retention_start(current_epoch)
    coverage_ms = spec.compute_slot_range_duration_ms(
        spec.compute_start_slot_at_epoch(start_epoch),
        spec.compute_start_slot_at_epoch(current_epoch),
    )
    assert window_ms <= coverage_ms < window_ms + spec.SLOTS_PER_EPOCH * max(pre_ms, post_ms)

    # One-time gas limit transition
    parent_gas_limit = spec.Uint64(60_000_000)
    assert spec.is_gas_limit_transition_compatible(
        parent_gas_limit,
        spec.Uint64(parent_gas_limit * post_ms // pre_ms),
        parent_gas_limit,
        spec.Slot(fork_slot - 1),
        fork_slot,
    )


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses non-default minimal slot durations")
@spec_configured_state_test(_alternate_config(4000), activate_at_genesis=True)
def test_alternate_duration_4000ms(spec, state):
    run_alternate_duration_checks(spec, state)


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses non-default minimal slot durations")
@spec_configured_state_test(_alternate_config(2000), activate_at_genesis=True)
def test_alternate_duration_2000ms(spec, state):
    run_alternate_duration_checks(spec, state)


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses non-default minimal slot durations")
@spec_configured_state_test(_alternate_config(9000), activate_at_genesis=True)
def test_alternate_duration_increase_9000ms(spec, state):
    run_alternate_duration_checks(spec, state)
