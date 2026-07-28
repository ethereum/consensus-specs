"""
Verify that changing only ``SLOT_DURATION_MS_EIP8198`` updates every
duration-dependent EIP-8198 rule.
"""

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL

ALTERNATE_FORK_EPOCH = 4096
ALTERNATE_SLOT_DURATION_MS = 4000
ALTERNATE_CONFIG = {
    "EIP8198_FORK_EPOCH": ALTERNATE_FORK_EPOCH,
    "SLOT_DURATION_MS_EIP8198": ALTERNATE_SLOT_DURATION_MS,
}


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses a non-default minimal slot duration")
@spec_configured_state_test(ALTERNATE_CONFIG, activate_at_genesis=True)
def test_alternate_duration_drives_time_network_and_gas(spec, state):
    pre_fork_duration = spec.config.SLOT_DURATION_MS
    post_fork_duration = spec.config.SLOT_DURATION_MS_EIP8198
    assert post_fork_duration == ALTERNATE_SLOT_DURATION_MS

    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(ALTERNATE_FORK_EPOCH))
    fork_time_ms = spec.compute_slot_start_time_ms(state.genesis_time, fork_slot)
    next_slot_time_ms = fork_time_ms + post_fork_duration
    assert spec.compute_slot_start_time_ms(state.genesis_time, spec.Slot(fork_slot + 1)) == (
        next_slot_time_ms
    )
    assert (
        spec.compute_slot_at_time_ms(state.genesis_time, spec.Uint64(next_slot_time_ms - 1))
        == fork_slot
    )
    assert spec.compute_slot_at_time_ms(state.genesis_time, next_slot_time_ms) == fork_slot + 1

    assert spec.get_attestation_due_ms() == (
        spec.config.ATTESTATION_DUE_BPS_GLOAS * post_fork_duration // spec.BASIS_POINTS
    )
    assert spec.get_inclusion_list_due_ms() == (
        spec.config.INCLUSION_LIST_DUE_BPS * post_fork_duration // spec.BASIS_POINTS
    )

    range_start = spec.Slot(fork_slot - spec.SLOTS_PER_EPOCH)
    range_end = spec.Slot(fork_slot + spec.SLOTS_PER_EPOCH)
    expected_range_ms = spec.SLOTS_PER_EPOCH * (pre_fork_duration + post_fork_duration)
    assert spec.compute_slot_range_duration_ms(range_start, range_end) == expected_range_ms
    assert spec.compute_seen_ttl(range_start) == expected_range_ms // 1000

    parent_gas_limit = spec.Uint64(60_000_000)
    expected_gas_limit = spec.Uint64(parent_gas_limit * post_fork_duration // pre_fork_duration)
    assert spec.is_gas_limit_target_compatible_eip8198(
        parent_gas_limit,
        expected_gas_limit,
        parent_gas_limit,
        spec.Slot(fork_slot - 1),
        fork_slot,
    )


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses a non-default minimal slot duration")
@spec_configured_state_test(ALTERNATE_CONFIG, activate_at_genesis=True)
def test_alternate_duration_drives_economics_and_churn(spec, state):
    pre_fork_duration = spec.config.SLOT_DURATION_MS
    post_fork_duration = spec.config.SLOT_DURATION_MS_EIP8198

    expected_base_reward = (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * post_fork_duration
        // pre_fork_duration
        // spec.integer_squareroot(spec.get_total_active_balance(state))
    )
    assert spec.get_base_reward_per_increment(state) == expected_base_reward

    index = 0
    state.inactivity_scores[index] = 1
    _, penalties = spec.get_inactivity_penalty_deltas(state)
    penalty_numerator = int(
        state.validators[index].effective_balance * state.inactivity_scores[index]
    )
    penalty_denominator = int(
        spec.config.INACTIVITY_SCORE_BIAS * spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
    )
    expected_penalty = (
        penalty_numerator
        * int(post_fork_duration)
        * int(post_fork_duration)
        // (penalty_denominator * int(pre_fork_duration) * int(pre_fork_duration))
    )
    assert penalties[index] == expected_penalty

    for validator in state.validators:
        validator.effective_balance = 0
    target_total = spec.Gwei(1_959_000_000_000)
    state.validators[0].effective_balance = target_total
    assert spec.get_total_active_balance(state) == target_total

    raw_activation_exit = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        target_total // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    raw_activation = min(
        spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS,
        raw_activation_exit,
    )
    expected_activation = raw_activation * post_fork_duration // pre_fork_duration
    expected_activation -= expected_activation % spec.EFFECTIVE_BALANCE_INCREMENT
    expected_exit = raw_activation_exit * post_fork_duration // pre_fork_duration
    expected_exit -= expected_exit % spec.EFFECTIVE_BALANCE_INCREMENT
    raw_consolidation = target_total // spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    expected_consolidation = raw_consolidation * post_fork_duration // pre_fork_duration
    expected_consolidation -= expected_consolidation % spec.EFFECTIVE_BALANCE_INCREMENT

    assert spec.get_activation_churn_limit(state) == expected_activation
    assert spec.get_exit_churn_limit(state) == expected_exit
    assert spec.get_consolidation_churn_limit(state) == expected_consolidation


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses a non-default minimal slot duration")
@spec_configured_state_test(ALTERNATE_CONFIG, activate_at_genesis=True)
def test_alternate_duration_drives_data_availability(spec, state):
    pre_fork_duration = spec.config.SLOT_DURATION_MS
    post_fork_duration = spec.config.SLOT_DURATION_MS_EIP8198
    fork_epoch = spec.Epoch(ALTERNATE_FORK_EPOCH)

    pre_fork_parameters = spec.get_blob_parameters(spec.Epoch(fork_epoch - 1))
    post_fork_parameters = spec.get_blob_parameters(fork_epoch)
    assert post_fork_parameters.max_blobs_per_block == (
        pre_fork_parameters.max_blobs_per_block * post_fork_duration // pre_fork_duration
    )

    pre_blob_epochs = spec.config.MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
    post_blob_epochs = pre_blob_epochs * pre_fork_duration // post_fork_duration
    blob_additional_epochs = post_blob_epochs - pre_blob_epochs
    blob_ramp_start = spec.Epoch(fork_epoch - blob_additional_epochs)
    assert spec.get_min_epochs_for_blob_sidecars_requests(blob_ramp_start) == pre_blob_epochs
    assert spec.get_min_epochs_for_blob_sidecars_requests(blob_ramp_start + 1) == (
        pre_blob_epochs + 1
    )
    assert spec.get_min_epochs_for_blob_sidecars_requests(fork_epoch) == post_blob_epochs

    pre_column_epochs = spec.config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    post_column_epochs = pre_column_epochs * pre_fork_duration // post_fork_duration
    column_additional_epochs = post_column_epochs - pre_column_epochs
    column_ramp_start = spec.Epoch(fork_epoch - column_additional_epochs)
    assert (
        spec.get_min_epochs_for_data_column_sidecars_requests(column_ramp_start)
        == pre_column_epochs
    )
    assert spec.get_min_epochs_for_data_column_sidecars_requests(column_ramp_start + 1) == (
        pre_column_epochs + 1
    )
    assert spec.get_min_epochs_for_data_column_sidecars_requests(fork_epoch) == post_column_epochs
