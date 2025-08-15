from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_to,
    with_phases,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.constants import (
    BELLATRIX,
    GLOAS,
)
from eth2spec.test.helpers.execution_payload import build_randomized_execution_payload
from eth2spec.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_empty_block_transition_no_tx(spec, state):
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    assert len(block.body.execution_payload.transactions) == 0

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_all_phases_from_to(BELLATRIX, GLOAS)
@spec_state_test
def test_block_transition_randomized_payload(spec, state):
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    next_slot_state = state.copy()
    next_slot(spec, next_slot_state)
    block.body.execution_payload = build_randomized_execution_payload(
        spec, next_slot_state, rng=Random(34433)
    )

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_phases([BELLATRIX])
@spec_state_test
def test_is_execution_enabled_false(spec, state):
    # Set `latest_execution_payload_header` to empty
    state.latest_execution_payload_header = spec.ExecutionPayloadHeader()
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    # Set `execution_payload` to empty
    block.body.execution_payload = spec.ExecutionPayload()
    assert len(block.body.execution_payload.transactions) == 0

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state
