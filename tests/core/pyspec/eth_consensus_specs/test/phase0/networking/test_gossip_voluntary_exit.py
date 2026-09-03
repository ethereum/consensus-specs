from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_all_phases,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    get_store_from_state,
    run_validate_gossip,
)
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


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__valid(spec, state):
    """
    Test that a valid voluntary exit passes gossip validation.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Pick a validator to exit
    validator_index = 0

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "valid",
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__ignore_already_seen(spec, state):
    """
    Test that a duplicate voluntary exit is ignored.
    """
    yield "topic", "meta", "voluntary_exit"

    messages = []
    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Pick a validator to exit
    validator_index = 0

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    # First validation should pass
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_exit),
            "expected": "valid",
        }
    )

    # Second validation should be ignored
    current_time_ms += 50
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "ignore"
    assert reason == "already seen voluntary exit for this validator"
    messages.append(
        {
            "offset_ms": 50,
            "message": get_filename(signed_exit),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__reject_validator_index_out_of_range(spec, state):
    """
    Test that a voluntary exit with validator index out of range is rejected.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Create voluntary exit with invalid validator index
    invalid_index = len(state.validators) + 100
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=invalid_index,
    )
    # Sign with any key (index 0)
    signed_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkeys[0])

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "reject"
    assert reason == "validator index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__reject_validator_not_active(spec, state):
    """
    Test that a voluntary exit for a non-active validator is rejected.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH

    # Pick a validator and make it inactive by setting activation_epoch to far future
    validator_index = 0
    state.validators[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "reject"
    assert reason == "validator is not active"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__ignore_already_initiated_exit(spec, state):
    """
    Test that a voluntary exit for a validator that has already initiated exit is ignored.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH

    # Pick a validator and set their exit_epoch (simulating already initiated exit)
    validator_index = 0
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 10
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "ignore"
    assert reason == "validator has already initiated exit"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__ignore_epoch_in_future(spec, state):
    """
    Test that a voluntary exit with epoch in the future is ignored.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Pick a validator
    validator_index = 0

    # Create voluntary exit with future epoch
    future_epoch = spec.get_current_epoch(state) + 10
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index, epoch=future_epoch)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "ignore"
    assert reason == "voluntary exit epoch is in the future"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__ignore_far_future_epoch(spec, state):
    """
    Test that a voluntary exit with the maximum Epoch is ignored without overflowing.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    signed_exit = create_signed_voluntary_exit(
        spec, state, validator_index=0, epoch=spec.FAR_FUTURE_EPOCH
    )
    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "ignore"
    assert reason == "voluntary exit epoch is in the future"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__ignore_before_clock_disparity(spec, state):
    """
    Test that a voluntary exit is ignored immediately before its epoch's
    clock-disparity window opens.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Keep the head state in the prior epoch while the next epoch's acceptance window opens.
    state.slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.config.SHARD_COMMITTEE_PERIOD))
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    exit_epoch = spec.get_current_epoch(state) + 1
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index=0, epoch=exit_epoch)
    yield get_filename(signed_exit), signed_exit

    epoch_start_slot = spec.compute_start_slot_at_epoch(exit_epoch)
    epoch_start_time_ms = spec.compute_time_at_slot_ms(store, epoch_start_slot)
    current_time_ms = epoch_start_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "ignore"
    assert reason == "voluntary exit epoch is in the future"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__valid_at_clock_disparity(spec, state):
    """
    Test that a voluntary exit is valid when its epoch's clock-disparity window
    opens while the head state is still in the previous epoch.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Keep the head state in the prior epoch while the next epoch's acceptance window opens.
    state.slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.config.SHARD_COMMITTEE_PERIOD))
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    exit_epoch = spec.get_current_epoch(state) + 1
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index=0, epoch=exit_epoch)
    yield get_filename(signed_exit), signed_exit

    epoch_start_slot = spec.compute_start_slot_at_epoch(exit_epoch)
    epoch_start_time_ms = spec.compute_time_at_slot_ms(store, epoch_start_slot)
    current_time_ms = epoch_start_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "valid",
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__valid_previous_epoch(spec, state):
    """
    Test that a voluntary exit with an epoch in the past is valid.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    exit_epoch = spec.get_current_epoch(state) - 1
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index=0, epoch=exit_epoch)
    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "valid",
            }
        ],
    )


@with_all_phases
@spec_state_test
def test_gossip_voluntary_exit__reject_not_active_long_enough(spec, state):
    """
    Test that a voluntary exit for a validator not active long enough is rejected.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Don't advance past SHARD_COMMITTEE_PERIOD - validator hasn't been active long enough
    # Just advance a few epochs
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Pick a validator
    validator_index = 0

    # Create voluntary exit
    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)

    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "reject"
    assert reason == "validator has not been active long enough"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases
@spec_state_test
@always_bls
def test_gossip_voluntary_exit__reject_invalid_signature(spec, state):
    """
    Test that a voluntary exit with invalid signature is rejected.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)

    # Advance state past SHARD_COMMITTEE_PERIOD
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

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

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "reject"
    assert reason == "invalid voluntary exit signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
