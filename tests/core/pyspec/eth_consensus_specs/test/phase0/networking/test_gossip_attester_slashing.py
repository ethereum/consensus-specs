from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth_consensus_specs.test.helpers.attester_slashings import (
    get_valid_attester_slashing,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen


def run_validate_attester_slashing_gossip(spec, seen, store, state, attester_slashing):
    """
    Run validate_attester_slashing_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_attester_slashing_gossip(seen, store, state, attester_slashing)
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__valid(spec, state):
    """
    Test that a valid attester slashing passes gossip validation.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid attester slashing
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"message": get_filename(attester_slashing), "expected": "valid"}],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__ignore_already_seen(spec, state):
    """
    Test that an attester slashing with all indices already seen is ignored.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid attester slashing
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield get_filename(attester_slashing), attester_slashing

    # First validation should pass
    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "valid"
    messages.append({"message": get_filename(attester_slashing), "expected": "valid"})

    # Second validation should be ignored (all indices already seen)
    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "ignore"
    assert reason == "all attester slashing indices already seen"
    messages.append(
        {
            "message": get_filename(attester_slashing),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_not_slashable_data(spec, state):
    """
    Test that an attester slashing with non-slashable attestation data is rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid attester slashing
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    # Make the attestation data identical (not a double vote or surround vote)
    attester_slashing.attestation_2.data = attester_slashing.attestation_1.data.copy()

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "attestation data is not slashable"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_invalid_attestation_1(spec, state):
    """
    Test that an attester slashing with invalid first attestation is rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create an attester slashing with only second attestation signed
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "invalid indexed attestation 1"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_invalid_attestation_2(spec, state):
    """
    Test that an attester slashing with invalid second attestation is rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create an attester slashing with only first attestation signed
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "invalid indexed attestation 2"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_attesting_index_out_of_range_1(spec, state):
    """
    Test that out-of-range attesting indices in attestation_1 are rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    invalid_index = len(state.validators) + 1
    attester_slashing.attestation_1.attesting_indices = [invalid_index]
    attester_slashing.attestation_2.attesting_indices = [invalid_index]

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "invalid indexed attestation 1"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_attesting_index_out_of_range_2(spec, state):
    """
    Test that out-of-range attesting indices in attestation_2 are rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    invalid_index = len(state.validators) + 1
    valid_index = int(attester_slashing.attestation_1.attesting_indices[0])
    attester_slashing.attestation_2.attesting_indices = [valid_index, invalid_index]

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "invalid indexed attestation 2"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__ignore_empty_attesting_indices_1(spec, state):
    """
    Test that empty attesting indices in attestation_1 are ignored by early dedup check.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    attester_slashing.attestation_1.attesting_indices = []

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "ignore"
    assert reason == "all attester slashing indices already seen"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__ignore_empty_attesting_indices_2(spec, state):
    """
    Test that empty attesting indices in attestation_2 are ignored by early dedup check.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    attester_slashing.attestation_2.attesting_indices = []

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "ignore"
    assert reason == "all attester slashing indices already seen"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_unsorted_indices_1(spec, state):
    """
    Test that an attester slashing with unsorted attestation_2 indices is rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid attester slashing
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    # Make attestation_1 have unsorted indices (will fail is_valid_indexed_attestation)
    # The indices need to still have an intersection with attestation_2
    original_indices = list(attester_slashing.attestation_1.attesting_indices)
    if len(original_indices) >= 2:
        # Reverse to make unsorted
        unsorted_indices = original_indices[::-1]
        attester_slashing.attestation_1.attesting_indices = unsorted_indices

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "invalid indexed attestation 1"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_unsorted_indices_2(spec, state):
    """
    Test that an attester slashing with unsorted attestation_2 indices is rejected.
    """
    yield "topic", "meta", "attester_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    original_indices = list(attester_slashing.attestation_2.attesting_indices)
    if len(original_indices) >= 2:
        attester_slashing.attestation_2.attesting_indices = original_indices[::-1]

    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "invalid indexed attestation 2"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_attester_slashing__reject_no_slashable_validators(spec, state):
    """
    Test that an attester slashing with no slashable validators is rejected.
    """
    yield "topic", "meta", "attester_slashing"

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid attester slashing
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    # Mark all validators in the intersection as already slashed
    indices = set(attester_slashing.attestation_1.attesting_indices).intersection(
        attester_slashing.attestation_2.attesting_indices
    )
    for index in indices:
        state.validators[index].slashed = True

    yield "state", state
    yield get_filename(attester_slashing), attester_slashing

    result, reason = run_validate_attester_slashing_gossip(
        spec, seen, store, state, attester_slashing
    )
    assert result == "reject"
    assert reason == "no slashable validators in intersection"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(attester_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
