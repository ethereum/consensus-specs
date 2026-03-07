from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import PHASE0
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    next_epoch_via_block,
)
from eth_consensus_specs.test.helpers.voluntary_exits import (
    sign_voluntary_exit,
)


def create_signed_voluntary_exit(spec, state, validator_index, epoch=None):
    """
    Create a valid SignedVoluntaryExit for the given validator.
    """
    if epoch is None:
        epoch = spec.get_current_epoch(state)

    voluntary_exit = spec.VoluntaryExit(
        epoch=epoch,
        validator_index=validator_index,
    )
    return sign_voluntary_exit(spec, state, voluntary_exit, privkeys[validator_index])


def run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_voluntary_exit):
    """
    Run validate_voluntary_exit_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_voluntary_exit_gossip(seen, store, state, signed_voluntary_exit)
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__valid(spec, state):
    """
    Test that a valid voluntary exit passes gossip validation.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD so validators can exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield "state", state

    # Pick a validator to exit
    validator_index = 0

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield "messages", "meta", [{"message": get_filename(signed_exit), "expected": "valid"}]


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__ignore_already_seen(spec, state):
    """
    Test that a duplicate voluntary exit is ignored.
    """
    yield "topic", "meta", "voluntary_exit"

    messages = []
    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield "state", state

    # Pick a validator to exit
    validator_index = 0

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    # First validation should pass
    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "valid"
    messages.append({"message": get_filename(signed_exit), "expected": "valid"})

    # Second validation should be ignored
    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "ignore"
    assert reason == "already seen voluntary exit for this validator"
    messages.append({"message": get_filename(signed_exit), "expected": "ignore", "reason": reason})

    yield "messages", "meta", messages


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__reject_validator_index_out_of_range(spec, state):
    """
    Test that a voluntary exit with validator index out of range is rejected.
    """
    yield "topic", "meta", "voluntary_exit"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Create voluntary exit with invalid validator index
    invalid_index = len(state.validators) + 100
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=invalid_index,
    )
    # Sign with any key (index 0)
    signed_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkeys[0])

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "reject"
    assert reason == "validator index out of range"

    yield (
        "messages",
        "meta",
        [{"message": get_filename(signed_exit), "expected": "reject", "reason": reason}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__reject_validator_not_active(spec, state):
    """
    Test that a voluntary exit for a non-active validator is rejected.
    """
    yield "topic", "meta", "voluntary_exit"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Pick a validator and make it inactive by setting activation_epoch to far future
    validator_index = 0
    state.validators[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "reject"
    assert reason == "validator is not active"

    yield (
        "messages",
        "meta",
        [{"message": get_filename(signed_exit), "expected": "reject", "reason": reason}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__reject_already_initiated_exit(spec, state):
    """
    Test that a voluntary exit for a validator that has already initiated exit is rejected.
    """
    yield "topic", "meta", "voluntary_exit"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Pick a validator and set their exit_epoch (simulating already initiated exit)
    validator_index = 0
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 10

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "reject"
    assert reason == "validator has already initiated exit"

    yield (
        "messages",
        "meta",
        [{"message": get_filename(signed_exit), "expected": "reject", "reason": reason}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__reject_epoch_in_future(spec, state):
    """
    Test that a voluntary exit with epoch in the future is rejected.
    """
    yield "topic", "meta", "voluntary_exit"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Pick a validator
    validator_index = 0

    # Create voluntary exit with future epoch
    future_epoch = spec.get_current_epoch(state) + 10
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index, epoch=future_epoch)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "reject"
    assert reason == "voluntary exit epoch is in the future"

    yield (
        "messages",
        "meta",
        [{"message": get_filename(signed_exit), "expected": "reject", "reason": reason}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__reject_not_active_long_enough(spec, state):
    """
    Test that a voluntary exit for a validator not active long enough is rejected.
    """
    yield "topic", "meta", "voluntary_exit"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Don't advance past SHARD_COMMITTEE_PERIOD - validator hasn't been active long enough
    # Just advance a few epochs
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    # Pick a validator
    validator_index = 0

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "reject"
    assert reason == "validator has not been active long enough"

    yield (
        "messages",
        "meta",
        [{"message": get_filename(signed_exit), "expected": "reject", "reason": reason}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_voluntary_exit__reject_invalid_signature(spec, state):
    """
    Test that a voluntary exit with invalid signature is rejected.
    """
    yield "topic", "meta", "voluntary_exit"
    yield "state", state

    seen = get_seen(spec)
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Pick a validator
    validator_index = 0

    # Create voluntary exit but sign with wrong key
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    # Sign with a different validator's key
    wrong_key = privkeys[validator_index + 1]
    signed_exit = sign_voluntary_exit(spec, state, voluntary_exit, wrong_key)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_voluntary_exit_gossip(spec, seen, store, state, signed_exit)
    assert result == "reject"
    assert reason == "invalid voluntary exit signature"

    yield (
        "messages",
        "meta",
        [{"message": get_filename(signed_exit), "expected": "reject", "reason": reason}],
    )
