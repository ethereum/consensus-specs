from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_except,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.constants import (
    BELLATRIX,
    EIP7732,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_state_with_complete_transition,
    build_state_with_incomplete_transition,
)


@with_bellatrix_and_later
@spec_state_test
def test_fail_merge_complete(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    assert not spec.is_merge_transition_complete(state)


@with_bellatrix_and_later
@spec_state_test
def test_success_merge_complete(spec, state):
    state = build_state_with_complete_transition(spec, state)
    assert spec.is_merge_transition_complete(state)


# with_complete_transition', 'with_execution_payload', 'is_merge_transition_block', 'is_execution_enabled'
expected_results = [
    (True, True, False, True),
    (True, False, False, True),
    (False, True, True, True),
    (False, False, False, False),
]


@with_all_phases_from_except(BELLATRIX, [EIP7732])
@spec_state_test
def test_is_merge_block_and_is_execution_enabled(spec, state):
    for result in expected_results:
        (
            with_complete_transition,
            with_execution_payload,
            is_merge_transition_block,
            is_execution_enabled,
        ) = result
        if with_complete_transition:
            state = build_state_with_complete_transition(spec, state)
        else:
            state = build_state_with_incomplete_transition(spec, state)

        body = spec.BeaconBlockBody()
        if with_execution_payload:
            body.execution_payload = build_empty_execution_payload(spec, state)

        assert spec.is_merge_transition_block(state, body) == is_merge_transition_block
        assert spec.is_execution_enabled(state, body) == is_execution_enabled
