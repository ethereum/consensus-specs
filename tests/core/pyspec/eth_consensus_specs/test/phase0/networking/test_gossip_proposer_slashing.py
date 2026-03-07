from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.proposer_slashings import (
    get_valid_proposer_slashing,
)


def run_validate_proposer_slashing_gossip(spec, seen, store, state, proposer_slashing):
    """
    Run validate_proposer_slashing_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_proposer_slashing_gossip(seen, store, state, proposer_slashing)
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__valid(spec, state):
    """
    Test that a valid proposer slashing passes gossip validation.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"message": get_filename(proposer_slashing), "expected": "valid"}],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__ignore_already_seen(spec, state):
    """
    Test that a duplicate proposer slashing is ignored.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    yield get_filename(proposer_slashing), proposer_slashing

    # First validation should pass
    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "valid"
    messages.append({"message": get_filename(proposer_slashing), "expected": "valid"})

    # Second validation should be ignored
    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "ignore"
    assert reason == "already seen proposer slashing for this proposer"
    messages.append(
        {
            "message": get_filename(proposer_slashing),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_slots_not_matching(spec, state):
    """
    Test that a proposer slashing with mismatched header slots is rejected.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # Modify second header slot to not match
    proposer_slashing.signed_header_2.message.slot = (
        proposer_slashing.signed_header_1.message.slot + 1
    )

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "header slots do not match"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_proposer_indices_not_matching(spec, state):
    """
    Test that a proposer slashing with mismatched proposer indices is rejected.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # Modify second header proposer_index to not match
    proposer_slashing.signed_header_2.message.proposer_index = (
        proposer_slashing.signed_header_1.message.proposer_index + 1
    )

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "header proposer indices do not match"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_headers_identical(spec, state):
    """
    Test that a proposer slashing with identical headers is rejected.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # Make headers identical by copying header_1 to header_2
    proposer_slashing.signed_header_2 = proposer_slashing.signed_header_1.copy()

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "headers are not different"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_proposer_index_out_of_range(spec, state):
    """
    Test that a proposer slashing with proposer index out of range is rejected.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # Set proposer index to be out of range
    invalid_index = len(state.validators) + 100
    proposer_slashing.signed_header_1.message.proposer_index = invalid_index
    proposer_slashing.signed_header_2.message.proposer_index = invalid_index

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "proposer index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_proposer_not_slashable(spec, state):
    """
    Test that a proposer slashing for a non-slashable proposer is rejected.
    """
    yield "topic", "meta", "proposer_slashing"

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a valid proposer slashing
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index

    # Make the proposer not slashable by setting slashed=True
    state.validators[proposer_index].slashed = True

    yield "state", state
    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "proposer is not slashable"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_invalid_signature_1(spec, state):
    """
    Test that a proposer slashing with invalid first signature is rejected.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a proposer slashing with only second header signed
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=False, signed_2=True)

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "invalid proposer slashing signature"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_proposer_slashing__reject_invalid_signature_2(spec, state):
    """
    Test that a proposer slashing with invalid second signature is rejected.
    """
    yield "topic", "meta", "proposer_slashing"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Create a proposer slashing with only first header signed
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=False)

    yield get_filename(proposer_slashing), proposer_slashing

    result, reason = run_validate_proposer_slashing_gossip(
        spec, seen, store, state, proposer_slashing
    )
    assert result == "reject"
    assert reason == "invalid proposer slashing signature"

    yield (
        "messages",
        "meta",
        [
            {
                "message": get_filename(proposer_slashing),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
