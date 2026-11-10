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
from eth_consensus_specs.test.helpers.constants import MINIMAL, PQ
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
    set_eth1_withdrawal_credential_with_balance,
)


def prepare_consolidation_request(spec, state, source_index, target_index, address, prefix=None):
    """
    A consolidation request naming the XMSS public keys of the validators at
    ``source_index`` and ``target_index``, each after ``prefix``.
    """
    if prefix is None:
        prefix = spec.XMSS_DEPOSIT_PREFIX
    return spec.ConsolidationRequest(
        source_address=address,
        source_pubkey=spec.Bytes48(prefix + state.validators[source_index].pubkey),
        target_pubkey=spec.Bytes48(prefix + state.validators[target_index].pubkey),
    )


def run_consolidation_request_processing(spec, state, consolidation_request):
    yield "pre", state
    yield "consolidation_request", consolidation_request

    spec.process_consolidation_request(state, consolidation_request)

    yield "post", state


@with_phases([PQ])
@spec_state_test
def test_switch_to_compounding(spec, state):
    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    request = prepare_consolidation_request(spec, state, validator_index, validator_index, address)

    yield from run_consolidation_request_processing(spec, state, request)

    assert spec.has_compounding_withdrawal_credential(state.validators[validator_index])


@with_phases([PQ])
@spec_state_test
def test_switch_to_compounding_legacy_pubkey_ignored(spec, state):
    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    request = prepare_consolidation_request(
        spec, state, validator_index, validator_index, address, prefix=b"\xff" * 16
    )
    pre_state = state.copy()

    yield from run_consolidation_request_processing(spec, state, request)

    assert state == pre_state


@with_phases([PQ])
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index, address=address)
    set_compounding_withdrawal_credential(spec, state, target_index)
    request = prepare_consolidation_request(spec, state, source_index, target_index, address)

    yield from run_consolidation_request_processing(spec, state, request)

    assert state.validators[source_index].exit_epoch < spec.FAR_FUTURE_EPOCH
    assert len(state.pending_consolidations) == 1
    assert state.pending_consolidations[0].source_index == source_index
    assert state.pending_consolidations[0].target_index == target_index
