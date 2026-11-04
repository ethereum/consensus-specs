from eth_consensus_specs.test.helpers.constants import (
    PQ,
)
from eth_consensus_specs.test.helpers.keys import get_vrf_data, xmss_builder_pubkeys, xmss_pubkeys

PQ_FORK_TEST_META_TAGS = {
    "fork": PQ,
}


def get_registration_pq_data(xmss_pubkey, vrf_data):
    """
    The PQ material of a registration, the XMSS public key followed by VRF data.
    """
    return xmss_pubkey + vrf_data


def register_xmss_pubkeys(spec, state, indices=None):
    """
    Add a pqreg registration of each validator's XMSS public key and VRF data.
    """
    if indices is None:
        indices = range(len(state.validators))
    for index in indices:
        state.validator_pq_registrations.append(
            spec.ValidatorPQRegistration(
                validator_index=index,
                pq_data=get_registration_pq_data(xmss_pubkeys[index], get_vrf_data(index)),
            )
        )


def register_builder_xmss_pubkeys(spec, state, indices=None):
    """
    Add a pqreg registration of each builder's XMSS public key.
    """
    if indices is None:
        indices = range(len(state.builders))
    for index in indices:
        state.builder_pq_registrations.append(
            spec.BuilderPQRegistration(
                builder_pubkey=state.builders[index].pubkey, pq_data=xmss_builder_pubkeys[index]
            )
        )


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_pq(pre_state.copy())

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
        "justification_bits",
        "previous_justified_checkpoint",
        "current_justified_checkpoint",
        "finalized_checkpoint",
        "latest_block_hash",
        "next_withdrawal_index",
        "next_withdrawal_validator_index",
        "historical_summaries",
        "deposit_requests_start_index",
        "deposit_balance_to_consume",
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

    # Every validator moves to the PQ registry at the same index
    registered = {
        int(registration.validator_index): registration.pq_data
        for registration in pre_state.validator_pq_registrations
    }
    assert len(post_state.pq_validators) == len(pre_state.validators)
    for index, (pre_validator, post_validator) in enumerate(
        zip(pre_state.validators, post_state.pq_validators, strict=True)
    ):
        assert post_validator.withdrawal_credentials == pre_validator.withdrawal_credentials
        assert post_validator.effective_balance == pre_validator.effective_balance
        assert post_validator.slashed == pre_validator.slashed
        assert post_validator.activation_epoch == pre_validator.activation_epoch
        if index in registered:
            pq_data = registered[index]
            assert post_validator.pubkey == pq_data[:32]
            assert post_validator.vrf_data == pq_data[32:]
            assert post_validator.exit_epoch == pre_validator.exit_epoch
        else:
            assert post_validator.pubkey == post_spec.XMSSPubkey()
            assert post_validator.vrf_data == post_spec.Bytes32()
            assert post_validator.exit_epoch != post_spec.FAR_FUTURE_EPOCH

    # Sync committees are removed
    assert not hasattr(post_state, "current_sync_committee")
    assert not hasattr(post_state, "next_sync_committee")

    # Every builder moves to the PQ registry at the same index
    registered_builders = {
        registration.builder_pubkey: registration.pq_data
        for registration in pre_state.builder_pq_registrations
    }
    assert len(post_state.pq_builders) == len(pre_state.builders)
    for pre_builder, post_builder in zip(pre_state.builders, post_state.pq_builders, strict=True):
        assert post_builder.execution_address == pre_builder.execution_address
        assert post_builder.balance == pre_builder.balance
        if pre_builder.pubkey in registered_builders:
            assert post_builder.pubkey == registered_builders[pre_builder.pubkey]
            assert post_builder.withdrawable_epoch == pre_builder.withdrawable_epoch
        else:
            assert post_builder.pubkey == post_spec.XMSSPubkey()
            assert post_builder.withdrawable_epoch != post_spec.FAR_FUTURE_EPOCH
    assert len(post_state.pending_builder_deposits) == 0

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.PQ_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
