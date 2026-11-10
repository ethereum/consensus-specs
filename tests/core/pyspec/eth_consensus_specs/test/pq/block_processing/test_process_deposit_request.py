from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.keys import get_vrf_root, privkeys, pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    build_pq_stored_preregistration,
    preregistration_withdrawal_credentials,
)

FRESH_INDEX = len(privkeys) - 1


def prepare_fresh_deposit_request(spec, state, withdrawal_credentials, index=FRESH_INDEX):
    """
    A deposit request for the XMSS key at ``index``, carrying its VRF root.
    """
    return prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=pubkeys[index],
        privkey=privkeys[index],
        withdrawal_credentials=withdrawal_credentials,
    )


def add_active_preregistration(spec, state, index=FRESH_INDEX):
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(spec, index, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS)
    )


def run_deposit_request_processing(spec, state, deposit_request):
    yield "pre", state
    yield "deposit_request", deposit_request

    spec.process_deposit_request(state, deposit_request)

    yield "post", state


@with_phases([PQ])
@spec_state_test
def test_deposit_request_matching_preregistration(spec, state):
    add_active_preregistration(spec, state)
    deposit_request = prepare_fresh_deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec)
    )
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert len(state.pending_deposits) == pre_pending_deposits + 1
    assert state.pending_deposits[-1].pubkey == deposit_request.pubkey
    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_deposit_request_preregistration_mismatched_credentials_discarded(spec, state):
    add_active_preregistration(spec, state)
    deposit_request = prepare_fresh_deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert len(state.pending_deposits) == pre_pending_deposits
    assert len(state.validator_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_deposit_request_preregistration_mismatched_vrf_root_discarded(spec, state):
    add_active_preregistration(spec, state)
    deposit_request = prepare_fresh_deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec)
    )
    deposit_request.signature = spec.Bytes96(get_vrf_root(0) + bytes(64))
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert len(state.pending_deposits) == pre_pending_deposits
    assert len(state.validator_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_deposit_request_expired_preregistration_not_enforced(spec, state):
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(spec, FRESH_INDEX, state.latest_execution_payload_bid.slot)
    )
    deposit_request = prepare_fresh_deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert len(state.pending_deposits) == pre_pending_deposits + 1
    assert len(state.validator_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_deposit_request_after_preregistration_consumed(spec, state):
    add_active_preregistration(spec, state)
    spec.process_deposit_request(
        state,
        prepare_fresh_deposit_request(spec, state, preregistration_withdrawal_credentials(spec)),
    )
    deposit_request = prepare_fresh_deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec, b"\x77")
    )
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert len(state.pending_deposits) == pre_pending_deposits + 1
    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_deposit_request_consumes_preregistration_preserving_order(spec, state):
    add_active_preregistration(spec, state, FRESH_INDEX - 1)
    add_active_preregistration(spec, state)
    add_active_preregistration(spec, state, FRESH_INDEX - 2)
    others = [state.validator_preregistrations[0], state.validator_preregistrations[2]]
    deposit_request = prepare_fresh_deposit_request(
        spec, state, preregistration_withdrawal_credentials(spec)
    )

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert list(state.validator_preregistrations) == others
