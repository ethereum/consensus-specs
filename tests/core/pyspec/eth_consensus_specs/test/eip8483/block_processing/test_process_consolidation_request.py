from eth_consensus_specs.test.context import (
    default_activation_threshold,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    single_phase,
    spec_test,
    with_custom_state,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.eip8483.block_processing.test_process_validator_pq_registration_request import (
    prepare_validator_pq_registration_request,
)
from eth_consensus_specs.test.electra.block_processing.test_process_consolidation_request import (
    run_consolidation_processing,
)
from eth_consensus_specs.test.helpers.constants import EIP8483, MINIMAL
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
    set_eth1_withdrawal_credential_with_balance,
)


@with_phases([EIP8483])
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_process_consolidation_request__removes_source_pq_registration(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for consolidation
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index, address=source_address)
    set_compounding_withdrawal_credential(spec, state, target_index)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, source_index, b"\x33" * 64)
    )
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, target_index, b"\x44" * 64)
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    yield from run_consolidation_processing(spec, state, consolidation)

    assert [registration.validator_index for registration in state.validator_pq_registrations] == [
        target_index
    ]
