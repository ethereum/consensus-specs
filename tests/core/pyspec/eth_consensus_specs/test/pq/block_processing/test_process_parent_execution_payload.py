from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.deposits import prepare_deposit_request
from eth_consensus_specs.test.helpers.keys import privkeys, pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    build_pq_preregistration_request,
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
def test_parent_payload_preregistration_stored(spec, state):
    request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(data=[request]),
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
    preregistration_request = build_pq_preregistration_request(
        spec, state, FRESH_INDEX, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests(data=[deposit_request]),
        preregistrations=spec.PreregistrationRequests(data=[preregistration_request]),
    )
    pre_pending_deposits = len(state.pending_deposits)

    yield from run_parent_execution_payload_processing(spec, state, requests)

    assert len(state.pending_deposits) == pre_pending_deposits + 1
    assert len(state.validator_preregistrations) == 0


@with_phases([PQ])
@spec_state_test
def test_max_preregistration_requests(spec, state):
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            data=[spec.PreregistrationRequest()] * spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests)


@with_phases([PQ])
@spec_state_test
def test_invalid_too_many_preregistration_requests(spec, state):
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests(
            data=[spec.PreregistrationRequest()]
            * (spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD + 1)
        ),
    )

    yield from run_parent_execution_payload_processing(spec, state, requests, valid=False)
