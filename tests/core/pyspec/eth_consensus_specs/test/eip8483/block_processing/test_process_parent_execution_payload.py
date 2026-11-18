from eth_consensus_specs.test.context import (
    default_activation_threshold,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.eip8483.block_processing.test_process_builder_pq_registration_request import (
    prepare_builder_pq_registration_request,
)
from eth_consensus_specs.test.eip8483.block_processing.test_process_validator_pq_registration_request import (
    prepare_validator_pq_registration_request,
)
from eth_consensus_specs.test.gloas.block_processing.test_process_parent_execution_payload import (
    run_parent_execution_payload_processing,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    prepare_process_builder_deposit_request,
)
from eth_consensus_specs.test.helpers.constants import EIP8483, MINIMAL
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.keys import pubkeys
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_withdrawal_request,
    set_compounding_withdrawal_credential,
    set_eth1_withdrawal_credential_with_balance,
    set_parent_block_full,
)


def run_parent_execution_requests_processing(spec, state, requests):
    """
    Mark the parent block as full with a bid that commits to ``requests``, then
    run ``process_parent_execution_payload`` for a child block that carries them.
    """
    set_parent_block_full(spec, state)
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_phases([EIP8483])
@spec_state_test
def test_process_parent_execution_payload__switch_to_compounding_and_pq_registration(spec, state):
    """
    Test that a validator with 0x01 credentials can switch to compounding and
    register PQ data in the same payload, because consolidation requests are
    processed before validator PQ registration requests.
    """
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, 0, address=address)
    pubkey = state.validators[0].pubkey
    requests = spec.ExecutionRequests(
        consolidations=spec.ConsolidationRequests.of(
            spec.ConsolidationRequest(
                source_address=address,
                source_pubkey=pubkey,
                target_pubkey=pubkey,
            )
        ),
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64)
        ),
    )

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert spec.has_compounding_withdrawal_credential(state.validators[0])
    assert [registration.validator_index for registration in state.validator_pq_registrations] == [
        0
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_parent_execution_payload__full_exit_and_pq_registration(spec, state):
    """
    Test that a validator cannot register PQ data in the same payload as its
    full exit, because withdrawal requests are processed before validator PQ
    registration requests.
    """
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    set_compounding_withdrawal_credential(spec, state, 0)
    requests = spec.ExecutionRequests(
        withdrawals=spec.WithdrawalRequests.of(prepare_withdrawal_request(spec, state, 0)),
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64)
        ),
    )

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert state.validators[0].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert len(state.validator_pq_registrations) == 0


@with_phases([EIP8483])
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_process_parent_execution_payload__consolidation_and_source_pq_registration(spec, state):
    """
    Test that a consolidation source cannot register PQ data in the same
    payload as its consolidation, because consolidation requests are processed
    before validator PQ registration requests.
    """
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for consolidation
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_compounding_withdrawal_credential(spec, state, source_index, address=source_address)
    set_compounding_withdrawal_credential(spec, state, target_index)
    requests = spec.ExecutionRequests(
        consolidations=spec.ConsolidationRequests.of(
            spec.ConsolidationRequest(
                source_address=source_address,
                source_pubkey=state.validators[source_index].pubkey,
                target_pubkey=state.validators[target_index].pubkey,
            )
        ),
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            prepare_validator_pq_registration_request(spec, state, source_index, b"\x33" * 64)
        ),
    )

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert state.validators[source_index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert len(state.validator_pq_registrations) == 0


@with_phases([EIP8483])
@spec_state_test
def test_process_parent_execution_payload__deposit_and_pq_registration(spec, state):
    """
    Test that a new validator cannot register PQ data in the same payload as
    its deposit, because a deposit request only queues a pending deposit and
    the validator is added to the registry later, during epoch processing.
    """
    validator_index = len(state.validators)
    address = b"\x22" * 20
    requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(
            prepare_deposit_request(
                spec,
                validator_index,
                spec.MIN_ACTIVATION_BALANCE,
                withdrawal_credentials=spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + address,
                signed=True,
            )
        ),
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            spec.ValidatorPQRegistrationRequest(
                source_address=address,
                validator_pubkey=pubkeys[validator_index],
                pq_data=b"\x33" * 64,
            )
        ),
    )
    pre_pending_deposits_len = len(state.pending_deposits)

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits_len + 1
    assert len(state.validators) == validator_index
    assert len(state.validator_pq_registrations) == 0


@with_phases([EIP8483])
@spec_state_test
def test_process_parent_execution_payload__pq_registrations_with_same_pq_data(spec, state):
    """
    Test that when two validators register the same PQ data in one payload,
    the earlier request is accepted and the later one is ignored.
    """
    set_compounding_withdrawal_credential(spec, state, 0)
    set_compounding_withdrawal_credential(spec, state, 1)
    requests = spec.ExecutionRequests(
        validator_pq_registrations=spec.ValidatorPQRegistrationRequests.of(
            prepare_validator_pq_registration_request(spec, state, 1, b"\x33" * 64),
            prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64),
        ),
    )

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert [registration.validator_index for registration in state.validator_pq_registrations] == [
        1
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_parent_execution_payload__builder_deposit_and_pq_registration(spec, state):
    """
    Test that a new builder can register PQ data in the same payload as its
    deposit, because a builder deposit request adds the builder to the registry
    immediately and builder deposit requests are processed before builder PQ
    registration requests.
    """
    deposit_request = prepare_process_builder_deposit_request(spec, state, signed=True)
    requests = spec.ExecutionRequests(
        builder_deposits=spec.BuilderDepositRequests.of(deposit_request),
        builder_pq_registrations=spec.BuilderPQRegistrationRequests.of(
            spec.BuilderPQRegistrationRequest(
                source_address=deposit_request.withdrawal_credentials[12:],
                builder_pubkey=deposit_request.pubkey,
                pq_data=b"\x33" * 32,
            )
        ),
    )

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert deposit_request.pubkey in [builder.pubkey for builder in state.builders]
    assert [registration.builder_pubkey for registration in state.builder_pq_registrations] == [
        deposit_request.pubkey
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_parent_execution_payload__builder_exit_and_pq_registration(spec, state):
    """
    Test that a builder cannot register PQ data in the same payload as its
    exit, because builder exit requests are processed before builder PQ
    registration requests.
    """
    # Finalize the builder's deposit epoch so that it is active
    state.finalized_checkpoint.epoch = state.builders[0].deposit_epoch + 1
    builder = state.builders[0]
    requests = spec.ExecutionRequests(
        builder_exits=spec.BuilderExitRequests.of(
            spec.BuilderExitRequest(
                source_address=builder.execution_address,
                pubkey=builder.pubkey,
            )
        ),
        builder_pq_registrations=spec.BuilderPQRegistrationRequests.of(
            prepare_builder_pq_registration_request(spec, state, 0, b"\x33" * 32)
        ),
    )

    yield from run_parent_execution_requests_processing(spec, state, requests)

    assert state.builders[0].withdrawable_epoch != spec.FAR_FUTURE_EPOCH
    assert len(state.builder_pq_registrations) == 0
