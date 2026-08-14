from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_eip8321_and_later,
)
from eth_consensus_specs.test.helpers.eip8321.randao import (
    activate_commitment,
    get_commitment,
    get_signed_registration,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.forks import get_previous_fork_version
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys

# EIP-8321 is unscheduled, so it has no entry in `configs/` and the harness
# genesis state carries the previous scheduled fork's version instead. Tests set
# `state.fork.current_version` explicitly to get past the fork gate.


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_gossip_randao_commitment_registration__valid(spec, state):
    """A well-formed registration for an unregistered validator passes gossip."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(spec, state, validator_index=0)

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
def test_gossip_randao_commitment_registration__ignore_pre_eip8321_head_state(spec, state):
    """A head state that has not yet upgraded to EIP-8321 ignores registrations.

    The registration signature is fork-agnostic, so it stays valid on the
    preceding fork; only the gate stops it.
    """
    state.fork.current_version = get_previous_fork_version(spec, spec.fork)
    assert state.fork.current_version < spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(spec, state, validator_index=0)

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "ignore"
    assert reason == "head state is pre-eip8321"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_gossip_randao_commitment_registration__valid_post_eip8321_head_state(spec, state):
    """A head state on a fork after EIP-8321 still accepts registrations.

    The gate is ``<``, not ``!=``: registrations remain valid in later forks.
    """
    # Stand in for a hypothetical fork scheduled after EIP-8321.
    state.fork.current_version = spec.Version(b"\xff\xff\xff\xff")
    assert state.fork.current_version > spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(spec, state, validator_index=0)

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
def test_gossip_randao_commitment_registration__reject_validator_index_out_of_range(spec, state):
    """A registration for an unknown validator index must be rejected."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(
        spec,
        state,
        validator_index=len(state.validators),
        commitment=get_commitment(spec, 0),
        privkey=privkeys[0],
    )

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "reject"
    assert reason == "validator index out of range"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
def test_gossip_randao_commitment_registration__ignore_already_seen(spec, state):
    """The second registration seen for a validator is ignored."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(spec, state, validator_index=0)

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    # Prime `seen` as if this validator's registration had already been validated.
    seen.randao_commitment_registration_indices.add(spec.ValidatorIndex(0))
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "ignore"
    assert reason == "already seen RANDAO commitment registration for this validator"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
def test_gossip_randao_commitment_registration__reject_zero_commitment(spec, state):
    """A zero commitment is the unregistered sentinel and must be rejected."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(
        spec, state, validator_index=0, commitment=spec.Bytes32()
    )

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "reject"
    assert reason == "commitment is zero"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
def test_gossip_randao_commitment_registration__ignore_already_registered(spec, state):
    """A registration for a validator that already has an active commitment is ignored."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(spec, state, validator_index=0)
    activate_commitment(spec, state, validator_index=0)

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "ignore"
    assert reason == "validator is already registered"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
def test_gossip_randao_commitment_registration__ignore_already_pending(spec, state):
    """A registration is ignored while the validator has one pending in the queue."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(spec, state, validator_index=0)
    state.pending_randao_commitments.append(
        spec.PendingRandaoCommitment(
            validator_index=0,
            commitment=get_commitment(spec, 0),
            activation_epoch=spec.Epoch(spec.COMMITMENT_REGISTRATION_DELAY),
        )
    )

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "ignore"
    assert reason == "RANDAO commitment registration is already pending for this validator"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_gossip_randao_commitment_registration__reject_invalid_signature(spec, state):
    """A registration signed by the wrong key is rejected."""
    state.fork.current_version = spec.EIP8321_FORK_VERSION
    signed_registration = get_signed_registration(
        spec, state, validator_index=0, privkey=privkeys[1]
    )

    anchor_state = state.copy()
    yield "topic", "meta", "randao_commitment_registration"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    yield get_filename(signed_registration), signed_registration

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_registration=signed_registration,
    )
    assert result == "reject"
    assert reason == "invalid RANDAO commitment registration signature"
    messages.append(
        {
            "offset_ms": 0,
            "message": get_filename(signed_registration),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
