from random import Random

from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_all_phases_from_to,
    with_bellatrix_and_later,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import (
    BELLATRIX,
    GLOAS,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_randomized_execution_payload,
    build_state_with_complete_transition,
    build_state_with_incomplete_transition,
    compute_el_block_hash,
    get_execution_payload_header,
)
from eth_consensus_specs.test.helpers.forks import is_post_eip8025, is_post_gloas
from eth_consensus_specs.test.helpers.keys import builder_privkeys, privkeys
from eth_consensus_specs.test.helpers.state import next_slot


def run_execution_payload_processing(
    spec, state, execution_payload, valid=True, execution_valid=True
):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - execution details, to mock EVM execution ('execution.yml', a dict with 'execution_valid' key and boolean value)
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # Before Deneb, only `body.execution_payload` matters. `BeaconBlockBody` is just a wrapper.
    # After Gloas the execution payload is no longer in the body
    if is_post_gloas(spec):
        envelope = spec.ExecutionPayloadEnvelope(
            payload=execution_payload,
            beacon_block_root=state.latest_block_header.hash_tree_root(),
        )
        post_state = state.copy()
        post_state.latest_block_hash = execution_payload.block_hash
        envelope.state_root = post_state.hash_tree_root()
        if envelope.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
            privkey = privkeys[state.latest_block_header.proposer_index]
        else:
            privkey = builder_privkeys[envelope.builder_index]
        signature = spec.get_execution_payload_envelope_signature(
            state,
            envelope,
            privkey,
        )
        signed_envelope = spec.SignedExecutionPayloadEnvelope(
            message=envelope,
            signature=signature,
        )
        yield "signed_envelope", signed_envelope
    else:
        body = spec.BeaconBlockBody(execution_payload=execution_payload)
        yield "body", body

    yield "pre", state
    yield "execution", {"execution_valid": execution_valid}

    called_new_block = False

    class TestEngine(spec.NoopExecutionEngine):
        def verify_and_notify_new_payload(self, new_payload_request) -> bool:
            nonlocal called_new_block
            called_new_block = True
            assert new_payload_request.execution_payload == execution_payload
            return execution_valid

    def call_process_execution_payload():
        engine = TestEngine()
        if is_post_gloas(spec):
            spec.process_execution_payload(state, signed_envelope, engine)
        elif is_post_eip8025(spec):
            spec.process_execution_payload(state, body, engine, spec.PROOF_ENGINE)
        else:
            spec.process_execution_payload(state, body, engine)

    if not valid:
        expect_assertion_error(call_process_execution_payload)
        yield "post", None
        return

    call_process_execution_payload()

    # Make sure we called the engine
    assert called_new_block

    yield "post", state

    if is_post_gloas(spec):
        assert state.latest_block_hash == execution_payload.block_hash
    else:
        assert state.latest_execution_payload_header == get_execution_payload_header(
            spec, state, body.execution_payload
        )


def run_success_test(spec, state):
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_success_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)

    yield from run_success_test(spec, state)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_success_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)

    yield from run_success_test(spec, state)


def run_gap_slot_test(spec, state):
    next_slot(spec, state)
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_success_first_payload_with_gap_slot(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_gap_slot_test(spec, state)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_success_regular_payload_with_gap_slot(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_gap_slot_test(spec, state)


def run_bad_execution_test(spec, state):
    # completely valid payload, but execution itself fails (e.g. block exceeds gas limit)
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(
        spec, state, execution_payload, valid=False, execution_valid=False
    )


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_invalid_bad_execution_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_execution_test(spec, state)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_invalid_bad_execution_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_execution_test(spec, state)


@with_phases([BELLATRIX])
@spec_state_test
def test_bad_parent_hash_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = b"\x55" * 32
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_bad_parent_hash_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = spec.Hash32()
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


def run_bad_prev_randao_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.prev_randao = b"\x42" * 32
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_bad_prev_randao_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_prev_randao_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_bad_pre_randao_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_prev_randao_test(spec, state)


def run_bad_everything_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = spec.Hash32()
    execution_payload.prev_randao = spec.Bytes32()
    execution_payload.timestamp = 0
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_bad_everything_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_everything_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_bad_everything_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_everything_test(spec, state)


def run_bad_timestamp_test(spec, state, is_future):
    next_slot(spec, state)

    # execution payload
    execution_payload = build_empty_execution_payload(spec, state)
    if is_future:
        timestamp = execution_payload.timestamp + 1
    else:
        timestamp = execution_payload.timestamp - 1
    execution_payload.timestamp = timestamp
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_future_timestamp_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=True)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_future_timestamp_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=True)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_past_timestamp_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=False)


@with_bellatrix_and_later
@spec_state_test
def test_invalid_past_timestamp_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=False)


def run_non_empty_extra_data_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.extra_data = b"\x45" * 12
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)
    assert state.latest_execution_payload_header.extra_data == execution_payload.extra_data


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_non_empty_extra_data_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_non_empty_extra_data_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


def run_non_empty_transactions_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    num_transactions = 2
    execution_payload.transactions = [
        spec.Transaction(b"\x99" * 128) for _ in range(num_transactions)
    ]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)

    if not is_post_gloas(spec):
        assert (
            state.latest_execution_payload_header.transactions_root
            == execution_payload.transactions.hash_tree_root()
        )


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_non_empty_transactions_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_non_empty_transactions_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


def run_zero_length_transaction_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.transactions = [spec.Transaction(b"")]
    assert len(execution_payload.transactions[0]) == 0
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)

    if not is_post_gloas(spec):
        assert (
            state.latest_execution_payload_header.transactions_root
            == execution_payload.transactions.hash_tree_root()
        )


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_zero_length_transaction_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_zero_length_transaction_test(spec, state)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_zero_length_transaction_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_zero_length_transaction_test(spec, state)


def run_randomized_non_validated_execution_fields_test(spec, state, rng, execution_valid=True):
    next_slot(spec, state)
    execution_payload = build_randomized_execution_payload(spec, state, rng)

    if is_post_gloas(spec):
        state.latest_execution_payload_bid.block_hash = execution_payload.block_hash
        state.latest_execution_payload_bid.gas_limit = execution_payload.gas_limit
        state.latest_block_hash = execution_payload.parent_hash

    yield from run_execution_payload_processing(
        spec, state, execution_payload, valid=execution_valid, execution_valid=execution_valid
    )


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_randomized_non_validated_execution_fields_first_payload__execution_valid(spec, state):
    rng = Random(1111)
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(spec, state, rng)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_randomized_non_validated_execution_fields_regular_payload__execution_valid(spec, state):
    rng = Random(2222)
    state = build_state_with_complete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(spec, state, rng)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_invalid_randomized_non_validated_execution_fields_first_payload__execution_invalid(
    spec, state
):
    rng = Random(3333)
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(
        spec, state, rng, execution_valid=False
    )


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_invalid_randomized_non_validated_execution_fields_regular_payload__execution_invalid(
    spec, state
):
    rng = Random(4444)
    state = build_state_with_complete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(
        spec, state, rng, execution_valid=False
    )
