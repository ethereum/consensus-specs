BELLATRIX_FORK_TEST_META_TAGS = {
    "fork": "bellatrix",
}


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_bellatrix(pre_state)

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
    ]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)

    # Modified fields
    modified_fields = ["fork"]
    for field in modified_fields:
        assert getattr(pre_state, field) != getattr(post_state, field)

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.BELLATRIX_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)
    assert post_state.latest_execution_payload_header == post_spec.ExecutionPayloadHeader()

    yield "post", post_state
