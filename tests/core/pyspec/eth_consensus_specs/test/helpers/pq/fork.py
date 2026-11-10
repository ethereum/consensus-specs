from eth_consensus_specs.test.helpers.constants import (
    PQ,
)
from eth_consensus_specs.test.helpers.keys import get_vrf_root, xmss_builder_pubkeys, xmss_pubkeys

PQ_FORK_TEST_META_TAGS = {
    "fork": PQ,
}


def get_registration_pq_data(xmss_pubkey, vrf_root):
    """
    The PQ material of a registration, the XMSS public key followed by VRF root.
    """
    return xmss_pubkey + vrf_root


def register_xmss_pubkeys(spec, state, indices=None):
    """
    Add an EIP-8483 registration of each validator's XMSS public key and VRF root.
    """
    if indices is None:
        indices = range(len(state.validators))
    for index in indices:
        state.validator_pq_registrations.append(
            spec.ValidatorPQRegistration(
                validator_index=index,
                pq_data=get_registration_pq_data(xmss_pubkeys[index], get_vrf_root(index)),
            )
        )


def register_builder_xmss_pubkeys(spec, state, indices=None):
    """
    Add an EIP-8483 registration of each builder's XMSS public key.
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
        "pending_partial_withdrawals",
        "pending_consolidations",
        "proposer_lookahead",
        "next_withdrawal_builder_index",
        "execution_payload_availability",
        "latest_execution_payload_bid",
        "payload_expected_withdrawals",
        "ptc_window",
    ]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)
    assert len(post_state.validator_preregistrations) == 0

    # Every validator moves to the PQ registry at the same index
    registered = {
        int(registration.validator_index): registration.pq_data
        for registration in pre_state.validator_pq_registrations
    }
    assert len(post_state.validators) == len(pre_state.validators)
    for index, (pre_validator, post_validator) in enumerate(
        zip(pre_state.validators, post_state.validators, strict=True)
    ):
        assert post_validator.withdrawal_credentials == pre_validator.withdrawal_credentials
        assert post_validator.effective_balance == pre_validator.effective_balance
        assert post_validator.slashed == pre_validator.slashed
        assert post_validator.activation_epoch == pre_validator.activation_epoch
        if index in registered:
            pq_data = registered[index]
            assert post_validator.pubkey == pq_data[:32]
            assert post_validator.vrf_root == pq_data[32:]
            assert post_validator.exit_epoch == pre_validator.exit_epoch
        else:
            assert post_validator.pubkey == post_spec.sha256(
                pre_validator.pubkey + post_spec.LEGACY_XMSS_PUBKEY_DOMAIN
            )
            assert post_validator.vrf_root == post_spec.sha256(
                pre_validator.pubkey + post_spec.LEGACY_VRF_ROOT_DOMAIN
            )
            assert post_validator.exit_epoch <= post_state.fork.epoch
            if pre_validator.slashed:
                assert post_validator.withdrawable_epoch == pre_validator.withdrawable_epoch
            else:
                assert post_validator.withdrawable_epoch <= post_state.fork.epoch

    # Each pending deposit for an existing validator names its XMSS public key
    pre_pubkeys = [validator.pubkey for validator in pre_state.validators]
    assert len(post_state.pending_deposits) == len(pre_state.pending_deposits)
    for pre_deposit, post_deposit in zip(
        pre_state.pending_deposits, post_state.pending_deposits, strict=True
    ):
        assert post_deposit.withdrawal_credentials == pre_deposit.withdrawal_credentials
        assert post_deposit.amount == pre_deposit.amount
        assert post_deposit.signature == pre_deposit.signature
        assert post_deposit.slot == pre_deposit.slot
        if pre_deposit.pubkey in pre_pubkeys:
            post_validator = post_state.validators[pre_pubkeys.index(pre_deposit.pubkey)]
            assert post_deposit.pubkey == post_spec.XMSS_DEPOSIT_PREFIX + post_validator.pubkey
        else:
            assert post_deposit.pubkey == pre_deposit.pubkey

    # Sync committees are removed
    assert not hasattr(post_state, "current_sync_committee")
    assert not hasattr(post_state, "next_sync_committee")

    # Every builder moves to the PQ registry at the same index
    registered_builders = {
        registration.builder_pubkey: registration.pq_data
        for registration in pre_state.builder_pq_registrations
    }
    assert len(post_state.builders) == len(pre_state.builders)
    for pre_builder, post_builder in zip(pre_state.builders, post_state.builders, strict=True):
        assert post_builder.execution_address == pre_builder.execution_address
        assert post_builder.balance == pre_builder.balance
        if pre_builder.pubkey in registered_builders:
            assert post_builder.pubkey == registered_builders[pre_builder.pubkey]
            assert post_builder.withdrawable_epoch == pre_builder.withdrawable_epoch
        else:
            assert post_builder.pubkey == post_spec.sha256(
                pre_builder.pubkey + post_spec.LEGACY_XMSS_PUBKEY_DOMAIN
            )
            assert post_builder.withdrawable_epoch != post_spec.FAR_FUTURE_EPOCH

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.PQ_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
