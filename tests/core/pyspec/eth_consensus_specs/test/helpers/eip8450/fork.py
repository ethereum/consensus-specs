from eth_consensus_specs.test.helpers.constants import (
    EIP8450,
)

EIP8450_FORK_TEST_META_TAGS = {
    "fork": EIP8450,
}


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_eip8450(pre_state)

    # Stable fields
    stable_fields = [
        "genesis_time",
        "genesis_validators_root",
        "slot",
        "latest_block_header",
        "block_roots",
        "state_roots",
        "historical_roots",
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

    # Every validator starts without registered keys
    assert len(post_state.post_quantum_key_material) == len(post_state.validators)
    assert len(post_state.post_quantum_key_change_epochs) == len(post_state.validators)
    assert all(keys == post_spec.PQKeyMaterial() for keys in post_state.post_quantum_key_material)
    assert all(
        epoch == post_spec.FAR_FUTURE_EPOCH for epoch in post_state.post_quantum_key_change_epochs
    )

    # Every builder starts without registered keys, at its deposit epoch
    assert len(post_state.builder_post_quantum_key_material) == len(post_state.builders)
    assert len(post_state.builder_post_quantum_key_change_epochs) == len(post_state.builders)
    assert all(
        keys == post_spec.PQKeyMaterial() for keys in post_state.builder_post_quantum_key_material
    )
    for builder, epoch in zip(
        post_state.builders, post_state.builder_post_quantum_key_change_epochs, strict=True
    ):
        assert epoch == builder.deposit_epoch

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.EIP8450_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
