from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.bls_to_execution_changes import (
    get_signed_address_change as get_signed_bls_to_execution_change,
)
from eth_consensus_specs.test.helpers.constants import CAPELLA
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.keys import pubkeys


def run_validate_bls_to_execution_change_gossip(
    spec, seen, state, signed_bls_to_execution_change, current_time_ms
):
    """
    Run validate_bls_to_execution_change_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_bls_to_execution_change_gossip(
            seen, state, signed_bls_to_execution_change, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def get_capella_fork_time_ms(spec, state):
    """
    Return the current time in milliseconds at the Capella fork epoch.
    """
    capella_slot = spec.compute_start_slot_at_epoch(spec.config.CAPELLA_FORK_EPOCH)
    return spec.compute_time_at_slot_ms(state, capella_slot)


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 0})
def test_gossip_bls_to_execution_change__valid(spec, state):
    """
    Test that a valid `bls_to_execution_change` passes gossip validation.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    seen = get_seen(spec)
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(spec, state)
    current_time_ms = get_capella_fork_time_ms(spec, state)

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_bls_to_execution_change),
                "expected": "valid",
            }
        ],
    )


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 1})
def test_gossip_bls_to_execution_change__ignore_pre_capella(spec, state):
    """
    Test that a `bls_to_execution_change` before the Capella fork is ignored.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    seen = get_seen(spec)
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(spec, state)
    current_time_ms = spec.compute_time_at_slot_ms(state, spec.Slot(0))

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "ignore"
    assert reason == "current epoch is pre-capella"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_bls_to_execution_change),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 0})
def test_gossip_bls_to_execution_change__ignore_already_seen(spec, state):
    """
    Test that a duplicate `bls_to_execution_change` is ignored.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(spec, state)
    current_time_ms = get_capella_fork_time_ms(spec, state)

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_bls_to_execution_change),
            "expected": "valid",
        }
    )

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "ignore"
    assert reason == "already seen BLS to execution change for this validator"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_bls_to_execution_change),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 0})
def test_gossip_bls_to_execution_change__reject_validator_index_out_of_range(spec, state):
    """
    Test that a `bls_to_execution_change` with validator index out of range is rejected.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    seen = get_seen(spec)
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(
        spec, state, validator_index=len(state.validators)
    )
    current_time_ms = get_capella_fork_time_ms(spec, state)

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "reject"
    assert reason == "validator index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_bls_to_execution_change),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 0})
def test_gossip_bls_to_execution_change__reject_not_bls_credentials(spec, state):
    """
    Test that a `bls_to_execution_change` for a validator without BLS credentials is rejected.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    seen = get_seen(spec)
    validator_index = len(state.validators) // 2
    state.validators[validator_index].withdrawal_credentials = b"\x01" + b"\x00" * 11 + b"\x23" * 20
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(
        spec, state, validator_index=validator_index
    )
    current_time_ms = get_capella_fork_time_ms(spec, state)

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "reject"
    assert reason == "validator does not have BLS withdrawal credentials"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_bls_to_execution_change),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 0})
def test_gossip_bls_to_execution_change__reject_pubkey_mismatch(spec, state):
    """
    Test that a `bls_to_execution_change` with the wrong withdrawal pubkey is rejected.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    seen = get_seen(spec)
    validator_index = 2
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(
        spec,
        state,
        validator_index=validator_index,
        withdrawal_pubkey=pubkeys[0],
    )
    current_time_ms = get_capella_fork_time_ms(spec, state)

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "reject"
    assert reason == "pubkey does not match validator withdrawal credentials"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_bls_to_execution_change),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([CAPELLA])
@spec_configured_state_test({"CAPELLA_FORK_EPOCH": 0})
@always_bls
def test_gossip_bls_to_execution_change__reject_bad_signature(spec, state):
    """
    Test that a `bls_to_execution_change` with an invalid signature is rejected.
    """
    yield "topic", "meta", "bls_to_execution_change"
    yield "state", state

    seen = get_seen(spec)
    signed_bls_to_execution_change = get_signed_bls_to_execution_change(spec, state)
    signed_bls_to_execution_change.signature = spec.BLSSignature(b"\x42" * 96)
    current_time_ms = get_capella_fork_time_ms(spec, state)

    yield get_filename(signed_bls_to_execution_change), signed_bls_to_execution_change
    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_bls_to_execution_change_gossip(
        spec, seen, state, signed_bls_to_execution_change, current_time_ms
    )
    assert result == "reject"
    assert reason == "invalid BLS to execution change signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_bls_to_execution_change),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
