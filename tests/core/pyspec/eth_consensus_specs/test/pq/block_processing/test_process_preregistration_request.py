from eth_consensus_specs.test.context import spec_state_test, with_phases, with_presets
from eth_consensus_specs.test.helpers.constants import MINIMAL, PQ
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.keys import get_vrf_root, privkeys, pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    build_pq_preregistration_request,
    build_pq_stored_preregistration,
    preregistration_withdrawal_credentials,
)

FRESH_INDEX = len(privkeys) - 1


def run_preregistration_request_processing(spec, state, request):
    yield "pre", state
    yield "preregistration_request", request

    spec.process_preregistration_request(state, request)

    yield "post", state


def fill_preregistrations(spec, state, count, expiry_slot):
    for index in range(count):
        state.validator_preregistrations.append(
            build_pq_stored_preregistration(spec, FRESH_INDEX - 1 - index, expiry_slot)
        )


@with_phases([PQ])
@spec_state_test
def test_preregistration_stored(spec, state):
    withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    request = build_pq_preregistration_request(spec, state, FRESH_INDEX, withdrawal_credentials)

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == 1
    stored = state.validator_preregistrations[0]
    assert stored.pubkey == request.pubkey
    assert stored.withdrawal_credentials == withdrawal_credentials
    assert stored.vrf_root == get_vrf_root(FRESH_INDEX)
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_phases([PQ])
@spec_state_test
def test_preregistration_existing_validator_ignored(spec, state):
    request = build_pq_preregistration_request(
        spec, state, 0, preregistration_withdrawal_credentials(spec)
    )
    assert request.pubkey == state.validators[0].pubkey

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_preregistration_pending_deposit_ignored(spec, state):
    deposit_request = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=pubkeys[FRESH_INDEX],
        privkey=privkeys[FRESH_INDEX],
        withdrawal_credentials=preregistration_withdrawal_credentials(spec, b"\x77"),
    )
    spec.process_deposit_request(state, deposit_request)
    request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_preregistration_active_binding_ignored(spec, state):
    stored = build_pq_stored_preregistration(
        spec, FRESH_INDEX, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )
    state.validator_preregistrations.append(stored)
    request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec, b"\x77")
    )

    yield from run_preregistration_request_processing(spec, state, request)

    assert list(state.validator_preregistrations) == [stored]


@with_phases([PQ])
@spec_state_test
def test_preregistration_replaces_expired_binding(spec, state):
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(spec, FRESH_INDEX, state.latest_execution_payload_bid.slot)
    )
    withdrawal_credentials = preregistration_withdrawal_credentials(spec, b"\x77")
    request = build_pq_preregistration_request(spec, state, FRESH_INDEX, withdrawal_credentials)

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == 1
    stored = state.validator_preregistrations[0]
    assert stored.withdrawal_credentials == withdrawal_credentials
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_phases([PQ])
@with_presets([MINIMAL], reason="mainnet preregistration limit is too large to fill")
@spec_state_test
def test_preregistration_state_full_ignored(spec, state):
    fill_preregistrations(
        spec,
        state,
        spec.PREREGISTRATIONS_LIMIT,
        state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS,
    )
    request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT
    assert request.pubkey not in [record.pubkey for record in state.validator_preregistrations]


@with_phases([PQ])
@with_presets([MINIMAL], reason="mainnet preregistration limit is too large to fill")
@spec_state_test
def test_preregistration_admitted_when_full_of_expired_records(spec, state):
    fill_preregistrations(
        spec, state, spec.PREREGISTRATIONS_LIMIT, state.latest_execution_payload_bid.slot
    )
    request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1
    assert state.validator_preregistrations[-1].pubkey == request.pubkey


@with_phases([PQ])
@with_presets([MINIMAL], reason="mainnet preregistration limit is too large to fill")
@spec_state_test
def test_preregistration_replacement_respects_active_limit(spec, state):
    expired = build_pq_stored_preregistration(
        spec, FRESH_INDEX, state.latest_execution_payload_bid.slot
    )
    state.validator_preregistrations.append(expired)
    fill_preregistrations(
        spec,
        state,
        spec.PREREGISTRATIONS_LIMIT,
        state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS,
    )
    request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec, b"\x77")
    )

    yield from run_preregistration_request_processing(spec, state, request)

    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1
    assert state.validator_preregistrations[0] == expired
