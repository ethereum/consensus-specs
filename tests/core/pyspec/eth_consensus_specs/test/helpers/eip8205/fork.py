from eth_consensus_specs.test.helpers.constants import (
    EIP8205,
)

EIP8205_FORK_TEST_META_TAGS = {
    "fork": EIP8205,
}


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_eip8205(pre_state)

    # Stable fields
    stable_fields = [
        "genesis_time",
        "genesis_validators_root",
        "slot",
        "latest_block_header",
        "block_roots",
        "state_roots",
        "historical_roots",
        "eth1_data",
        "eth1_data_votes",
        "eth1_deposit_index",
        "validators",
        "balances",
        "randao_mixes",
        "slashings",
        "previous_epoch_participation",
        "current_epoch_participation",
        "justification_bits",
        "previous_justified_checkpoint",
        "current_justified_checkpoint",
        "finalized_checkpoint",
        "inactivity_scores",
        "current_sync_committee",
        "next_sync_committee",
        "latest_block_hash",
        "next_withdrawal_index",
        "next_withdrawal_validator_index",
        "historical_summaries",
        "deposit_requests_start_index",
        "deposit_balance_to_consume",
        "exit_balance_to_consume",
        "earliest_exit_epoch",
        "consolidation_balance_to_consume",
        "earliest_consolidation_epoch",
        "pending_deposits",
        "pending_partial_withdrawals",
        "pending_consolidations",
        "proposer_lookahead",
        "builders",
        "next_withdrawal_builder_index",
        "execution_payload_availability",
        "builder_pending_payments",
        "builder_pending_withdrawals",
        "latest_execution_payload_bid",
        "payload_expected_withdrawals",
        "ptc_window",
    ]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)

    # Modified fields
    modified_fields = ["fork"]
    for field in modified_fields:
        assert getattr(pre_state, field) != getattr(post_state, field)

    # No preregistration can exist before the fork
    assert len(post_state.validator_preregistrations) == 0

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.EIP8205_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
