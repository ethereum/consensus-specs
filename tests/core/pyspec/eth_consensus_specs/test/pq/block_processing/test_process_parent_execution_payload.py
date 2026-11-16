from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.keys import privkeys, pubkeys, xmss_builder_pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    build_pq_builder_preregistration_request,
    build_pq_validator_preregistration_request,
    builder_preregistration_withdrawal_credentials,
    preregistration_withdrawal_credentials,
)
from eth_consensus_specs.test.helpers.withdrawals import set_parent_block_full

FRESH_INDEX = len(privkeys) - 1


def run_parent_execution_payload_processing(spec, state, requests, valid=True):
    """
    Commit ``requests`` to a full parent and process them through the next
    block.
    """
    set_parent_block_full(spec, state)
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    spec.process_slots(state, block.slot)

    yield "pre", state
    yield "block", block

    if not valid:
        expect_assertion_error(lambda: spec.process_parent_execution_payload(state, block))
        yield "post", None
        return

    spec.process_parent_execution_payload(state, block)
    yield "post", state


@with_phases([PQ])
@spec_state_test
def test_parent_payload_validator_preregistration_stored(spec, state):
    request = build_pq_validator_preregistration_request(
        spec, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        validator_preregistrations=spec.ValidatorPreregistrationRequests(data=[request]),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == request.pubkey
    assert (
        state.validator_preregistrations[0].expiry_slot
        == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )


@with_phases([PQ])
@spec_state_test
def test_parent_payload_deposit_first_for_same_pubkey(spec, state):
    deposit_request = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        pubkey=pubkeys[FRESH_INDEX],
        privkey=privkeys[FRESH_INDEX],
        withdrawal_credentials=preregistration_withdrawal_credentials(spec, b"\x77"),
    )
    preregistration_request = build_pq_validator_preregistration_request(
        spec, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests(data=[deposit_request]),
        validator_preregistrations=spec.ValidatorPreregistrationRequests(
            data=[preregistration_request]
        ),
    )
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_parent_execution_payload_processing(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits + 1
    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_max_validator_preregistration_requests(spec, state):
    requests = spec.ExecutionRequests(
        validator_preregistrations=spec.ValidatorPreregistrationRequests(
            data=[spec.ValidatorPreregistrationRequest()]
            * spec.MAX_VALIDATOR_PREREGISTRATION_REQUESTS_PER_PAYLOAD
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)


@with_phases([PQ])
@spec_state_test
def test_invalid_too_many_validator_preregistration_requests(spec, state):
    requests = spec.ExecutionRequests(
        validator_preregistrations=spec.ValidatorPreregistrationRequests(
            data=[spec.ValidatorPreregistrationRequest()]
            * (spec.MAX_VALIDATOR_PREREGISTRATION_REQUESTS_PER_PAYLOAD + 1)
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests, valid=False)


@with_phases([PQ])
@spec_state_test
def test_parent_payload_builder_preregistration_stored(spec, state):
    request = build_pq_builder_preregistration_request(
        spec, len(xmss_builder_pubkeys) - 1, builder_preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        builder_preregistrations=spec.BuilderPreregistrationRequests(data=[request]),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)

    assert len(state.builder_preregistrations) == 1
    assert state.builder_preregistrations[0].pubkey == request.pubkey
    assert (
        state.builder_preregistrations[0].expiry_slot
        == state.slot + spec.PREREGISTRATION_EXPIRY_SLOTS
    )


@with_phases([PQ])
@spec_state_test
def test_max_builder_preregistration_requests(spec, state):
    requests = spec.ExecutionRequests(
        builder_preregistrations=spec.BuilderPreregistrationRequests(
            data=[spec.BuilderPreregistrationRequest()]
            * spec.MAX_BUILDER_PREREGISTRATION_REQUESTS_PER_PAYLOAD
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)


@with_phases([PQ])
@spec_state_test
def test_invalid_too_many_builder_preregistration_requests(spec, state):
    requests = spec.ExecutionRequests(
        builder_preregistrations=spec.BuilderPreregistrationRequests(
            data=[spec.BuilderPreregistrationRequest()]
            * (spec.MAX_BUILDER_PREREGISTRATION_REQUESTS_PER_PAYLOAD + 1)
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests, valid=False)


@with_phases([PQ])
@spec_state_test
def test_parent_payload_voluntary_exit_request(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = 0
    requests = spec.ExecutionRequests(
        voluntary_exits=spec.VoluntaryExitRequests(
            data=[spec.VoluntaryExitRequest(pubkey=state.validators[validator_index].pubkey)]
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_phases([PQ])
@spec_state_test
def test_max_voluntary_exit_requests(spec, state):
    requests = spec.ExecutionRequests(
        voluntary_exits=spec.VoluntaryExitRequests(
            data=[spec.VoluntaryExitRequest()] * spec.MAX_VOLUNTARY_EXIT_REQUESTS_PER_PAYLOAD
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)


@with_phases([PQ])
@spec_state_test
def test_invalid_too_many_voluntary_exit_requests(spec, state):
    requests = spec.ExecutionRequests(
        voluntary_exits=spec.VoluntaryExitRequests(
            data=[spec.VoluntaryExitRequest()] * (spec.MAX_VOLUNTARY_EXIT_REQUESTS_PER_PAYLOAD + 1)
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests, valid=False)
