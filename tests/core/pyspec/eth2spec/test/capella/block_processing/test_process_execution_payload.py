from eth2spec.test.bellatrix.block_processing.test_process_execution_payload import (
    run_execution_payload_processing,
)
from eth2spec.test.context import (
    spec_state_test,
    with_capella_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_state_with_incomplete_transition,
    compute_el_block_hash,
)
from eth2spec.test.helpers.state import next_slot


@with_capella_and_later
@spec_state_test
def test_invalid_bad_parent_hash_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = b"\x55" * 32
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)
