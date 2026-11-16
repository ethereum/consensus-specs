from eth_consensus_specs.test.context import spec_state_test, with_phases, with_presets
from eth_consensus_specs.test.helpers.constants import MINIMAL, PQ
from eth_consensus_specs.test.helpers.keys import xmss_builder_pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    build_pq_builder_preregistration,
    build_pq_builder_preregistration_request,
    build_pq_validator_preregistration,
    builder_preregistration_withdrawal_credentials,
)

FRESH_INDEX = len(xmss_builder_pubkeys) - 1


def run_builder_preregistration_request_processing(spec, state, request):
    yield "pre", state
    yield "builder_preregistration_request", request

    spec.process_builder_preregistration_request(state, request)

    yield "post", state


def fill_builder_preregistrations(spec, state, count, expiry_slot):
    for index in range(count):
        state.builder_preregistrations.append(
            build_pq_builder_preregistration(spec, FRESH_INDEX - 1 - index, expiry_slot)
        )


@with_phases([PQ])
@spec_state_test
def test_builder_preregistration_stored(spec, state):
    withdrawal_credentials = builder_preregistration_withdrawal_credentials(spec)
    request = build_pq_builder_preregistration_request(spec, FRESH_INDEX, withdrawal_credentials)

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == 1
    stored = state.builder_preregistrations[0]
    assert stored.pubkey == request.pubkey
    assert stored.withdrawal_credentials == withdrawal_credentials
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_builder_preregistration_existing_builder_ignored(spec, state):
    request = spec.BuilderPreregistrationRequest(
        pubkey=state.builders[0].pubkey,
        withdrawal_credentials=builder_preregistration_withdrawal_credentials(spec),
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_builder_preregistration_existing_validator_stored(spec, state):
    request = spec.BuilderPreregistrationRequest(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials=builder_preregistration_withdrawal_credentials(spec),
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == 1
    assert state.builder_preregistrations[0].pubkey == state.validators[0].pubkey


@with_phases([PQ])
@spec_state_test
def test_builder_preregistration_ignores_validator_preregistration(spec, state):
    validator_preregistration = build_pq_validator_preregistration(
        spec, 0, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )
    validator_preregistration.pubkey = xmss_builder_pubkeys[FRESH_INDEX]
    state.validator_preregistrations.append(validator_preregistration)
    request = build_pq_builder_preregistration_request(
        spec, FRESH_INDEX, builder_preregistration_withdrawal_credentials(spec)
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert list(state.validator_preregistrations) == [validator_preregistration]
    assert len(state.builder_preregistrations) == 1
    assert state.builder_preregistrations[0].pubkey == request.pubkey


@with_phases([PQ])
@spec_state_test
def test_builder_preregistration_active_binding_ignored(spec, state):
    stored = build_pq_builder_preregistration(
        spec, FRESH_INDEX, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )
    state.builder_preregistrations.append(stored)
    request = build_pq_builder_preregistration_request(
        spec, FRESH_INDEX, builder_preregistration_withdrawal_credentials(spec, b"\x77")
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert list(state.builder_preregistrations) == [stored]


@with_phases([PQ])
@spec_state_test
def test_builder_preregistration_replaces_expired_binding(spec, state):
    state.builder_preregistrations.append(
        build_pq_builder_preregistration(spec, FRESH_INDEX, state.latest_execution_payload_bid.slot)
    )
    withdrawal_credentials = builder_preregistration_withdrawal_credentials(spec, b"\x77")
    request = build_pq_builder_preregistration_request(spec, FRESH_INDEX, withdrawal_credentials)

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == 1
    stored = state.builder_preregistrations[0]
    assert stored.withdrawal_credentials == withdrawal_credentials
    assert stored.expiry_slot == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS


@with_phases([PQ])
@with_presets([MINIMAL], reason="mainnet preregistration limit is too large to fill")
@spec_state_test
def test_builder_preregistration_state_full_ignored(spec, state):
    fill_builder_preregistrations(
        spec,
        state,
        spec.PREREGISTRATIONS_LIMIT,
        state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS,
    )
    request = build_pq_builder_preregistration_request(
        spec, FRESH_INDEX, builder_preregistration_withdrawal_credentials(spec)
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == spec.PREREGISTRATIONS_LIMIT
    assert request.pubkey not in [record.pubkey for record in state.builder_preregistrations]


@with_phases([PQ])
@with_presets([MINIMAL], reason="mainnet preregistration limit is too large to fill")
@spec_state_test
def test_builder_preregistration_admitted_when_full_of_expired_records(spec, state):
    fill_builder_preregistrations(
        spec, state, spec.PREREGISTRATIONS_LIMIT, state.latest_execution_payload_bid.slot
    )
    request = build_pq_builder_preregistration_request(
        spec, FRESH_INDEX, builder_preregistration_withdrawal_credentials(spec)
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == spec.PREREGISTRATIONS_LIMIT + 1
    assert state.builder_preregistrations[-1].pubkey == request.pubkey


@with_phases([PQ])
@with_presets([MINIMAL], reason="mainnet preregistration limit is too large to fill")
@spec_state_test
def test_builder_preregistration_limit_ignores_validator_preregistrations(spec, state):
    for index in range(spec.PREREGISTRATIONS_LIMIT):
        state.validator_preregistrations.append(
            build_pq_validator_preregistration(
                spec, index, state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
            )
        )
    request = build_pq_builder_preregistration_request(
        spec, FRESH_INDEX, builder_preregistration_withdrawal_credentials(spec)
    )

    yield from run_builder_preregistration_request_processing(spec, state, request)

    assert len(state.builder_preregistrations) == 1
    assert state.builder_preregistrations[0].pubkey == request.pubkey
