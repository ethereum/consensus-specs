"""
Spot-check that derived EIP-8198 values follow ``SLOT_DURATION_MS_EIP8198``
under a non-default target duration, so no rule hard-codes the default ratio.
"""

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL

ALTERNATE_FORK_EPOCH = 4096
ALTERNATE_CONFIG = {
    "EIP8198_FORK_EPOCH": ALTERNATE_FORK_EPOCH,
    "SLOT_DURATION_MS_EIP8198": 4000,
}


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses a non-default minimal slot duration")
@spec_configured_state_test(ALTERNATE_CONFIG, activate_at_genesis=True)
def test_alternate_duration_drives_derived_values(spec, state):
    pre_ms = spec.config.SLOT_DURATION_MS
    post_ms = spec.config.SLOT_DURATION_MS_EIP8198
    assert post_ms == 4000

    # Piecewise timeline
    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(ALTERNATE_FORK_EPOCH))
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

    # Intra-slot deadlines
    assert spec.get_attestation_due_ms() == (
        spec.config.ATTESTATION_DUE_BPS_GLOAS * post_ms // spec.BASIS_POINTS
    )

    # Issuance and churn
    assert spec.get_base_reward_per_increment(state) == (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * post_ms
        // pre_ms
        // spec.integer_squareroot(spec.get_total_active_balance(state))
    )
    raw_exit = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        spec.get_total_active_balance(state) // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    expected_exit = raw_exit * post_ms // pre_ms
    expected_exit -= expected_exit % spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.get_exit_churn_limit(state) == expected_exit

    # Blob throughput and retention
    fork_epoch = spec.Epoch(ALTERNATE_FORK_EPOCH)
    pre_fork_parameters = spec.get_blob_parameters(spec.Epoch(fork_epoch - 1))
    assert spec.get_blob_parameters(fork_epoch).max_blobs_per_block == (
        pre_fork_parameters.max_blobs_per_block * post_ms // pre_ms
    )
    pre_blob_epochs = spec.config.MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
    post_blob_epochs = pre_blob_epochs * pre_ms // post_ms
    blob_growth = post_blob_epochs - pre_blob_epochs
    assert spec.get_min_epochs_for_blob_sidecars_requests(fork_epoch) == pre_blob_epochs
    assert spec.get_min_epochs_for_blob_sidecars_requests(spec.Epoch(fork_epoch + blob_growth)) == (
        post_blob_epochs
    )

    # One-time gas limit transition
    parent_gas_limit = spec.Uint64(60_000_000)
    assert spec.is_gas_limit_transition_compatible(
        parent_gas_limit,
        spec.Uint64(parent_gas_limit * post_ms // pre_ms),
        parent_gas_limit,
        spec.Slot(fork_slot - 1),
        fork_slot,
    )
