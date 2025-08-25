from eth2spec.test.helpers.constants import (
    DENEB,
)

DENEB_FORK_TEST_META_TAGS = {
    "fork": DENEB,
}


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_deneb(pre_state)

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
        "next_withdrawal_index",
        "next_withdrawal_validator_index",
        "historical_summaries",
    ]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)

    # Modified fields
    modified_fields = ["fork", "latest_execution_payload_header"]
    for field in modified_fields:
        assert getattr(pre_state, field) != getattr(post_state, field)

    assert len(pre_state.validators) == len(post_state.validators)
    for pre_validator, post_validator in zip(pre_state.validators, post_state.validators):
        stable_validator_fields = [
            "pubkey",
            "withdrawal_credentials",
            "effective_balance",
            "slashed",
            "activation_eligibility_epoch",
            "activation_epoch",
            "exit_epoch",
            "withdrawable_epoch",
        ]
        for field in stable_validator_fields:
            assert getattr(pre_validator, field) == getattr(post_validator, field)

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.DENEB_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state
