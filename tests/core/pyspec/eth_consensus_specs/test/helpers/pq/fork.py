from hashlib import sha256

from eth_consensus_specs.test.helpers.constants import (
    PQ,
)
from eth_consensus_specs.test.helpers.keys import xmss_builder_pubkeys, xmss_pubkeys

PQ_FORK_TEST_META_TAGS = {
    "fork": PQ,
}


def get_registration_pq_data(xmss_pubkey):
    """
    The PQ material of a registration, the XMSS public key followed by VRF data.
    """
    return xmss_pubkey + sha256(xmss_pubkey).digest()


def register_xmss_pubkeys(spec, state, indices=None):
    """
    Add an EIP-8483 registration of each validator's XMSS public key.
    """
    if indices is None:
        indices = range(len(state.validators))
    for index in indices:
        state.pq_registrations.append(
            spec.PQRegistration(
                role=spec.PQ_REGISTRATION_ROLE_VALIDATOR,
                pubkey=state.validators[index].pubkey,
                pq_data=get_registration_pq_data(xmss_pubkeys[index]),
            )
        )


def register_builder_xmss_pubkeys(spec, state, indices=None):
    """
    Add an EIP-8483 registration of each builder's XMSS public key.
    """
    if indices is None:
        indices = range(len(state.builders))
    for index in indices:
        state.pq_registrations.append(
            spec.PQRegistration(
                role=spec.PQ_REGISTRATION_ROLE_BUILDER,
                pubkey=state.builders[index].pubkey,
                pq_data=get_registration_pq_data(xmss_builder_pubkeys[index]),
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
        "pending_deposits",
        "pending_partial_withdrawals",
        "pending_consolidations",
        "proposer_lookahead",
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

    # Each registration becomes an entry of the PQ data
    assert len(post_state.pq_data) == len(pre_state.pq_registrations)
    for registration, entry in zip(pre_state.pq_registrations, post_state.pq_data, strict=True):
        assert entry.role == registration.role
        assert entry.bls_pubkey == registration.pubkey
        assert entry.xmss_pubkey == registration.pq_data[:32]
        assert entry.vrf_data == registration.pq_data[32:]

    # Validators keep their BLS public key, and those without an entry exit
    registered_pubkeys = post_spec.get_pq_data_pubkeys(
        post_state, post_spec.PQ_REGISTRATION_ROLE_VALIDATOR
    )
    assert len(post_state.validators) == len(pre_state.validators)
    for pre_validator, post_validator in zip(
        pre_state.validators, post_state.validators, strict=True
    ):
        assert post_validator.pubkey == pre_validator.pubkey
        assert post_validator.withdrawal_credentials == pre_validator.withdrawal_credentials
        assert post_validator.effective_balance == pre_validator.effective_balance
        assert post_validator.activation_epoch == pre_validator.activation_epoch
        if pre_validator.pubkey in registered_pubkeys:
            assert post_validator.exit_epoch == pre_validator.exit_epoch
        else:
            assert post_validator.exit_epoch != post_spec.FAR_FUTURE_EPOCH

    # Sync committees are removed
    assert not hasattr(post_state, "current_sync_committee")
    assert not hasattr(post_state, "next_sync_committee")

    # Builders keep their BLS public key, and those without an entry exit
    registered_builder_pubkeys = post_spec.get_pq_data_pubkeys(
        post_state, post_spec.PQ_REGISTRATION_ROLE_BUILDER
    )
    assert len(post_state.builders) == len(pre_state.builders)
    for pre_builder, post_builder in zip(pre_state.builders, post_state.builders, strict=True):
        assert post_builder.pubkey == pre_builder.pubkey
        assert post_builder.balance == pre_builder.balance
        if pre_builder.pubkey in registered_builder_pubkeys:
            assert post_builder.withdrawable_epoch == pre_builder.withdrawable_epoch
        else:
            assert post_builder.withdrawable_epoch != post_spec.FAR_FUTURE_EPOCH

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.PQ_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
