from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    with_eip8450_and_later,
)
from eth_consensus_specs.test.helpers.eip8450.pq_keys import (
    get_pq_public_keys,
    get_signed_pq_key_registration,
    get_xmss_secret_key,
    register_pq_keys,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    get_store_from_state,
    run_validate_gossip,
)
from eth_consensus_specs.test.helpers.keys import privkeys


def get_time_at_epoch_ms(spec, store, epoch):
    slot = spec.compute_start_slot_at_epoch(epoch)
    return spec.compute_time_at_slot_ms(store.genesis_time_ms, slot)


def run_pq_key_registration_gossip(spec, state, cases, epoch=None):
    """
    Validate each ``(signed_registration, expected, reason)`` of ``cases`` in
    order, sharing one ``Seen``, at the start of ``epoch``.
    """
    yield "topic", "meta", "pq_key_registration"
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    if epoch is None:
        epoch = spec.get_current_epoch(state)
    current_time_ms = get_time_at_epoch_ms(spec, store, epoch)

    seen = get_seen(spec)
    messages = []
    for signed_registration, expected, expected_reason in cases:
        yield get_filename(signed_registration), signed_registration

        result, reason = run_validate_gossip(
            spec,
            seen=seen,
            store=store,
            signed_registration=signed_registration,
            current_time_ms=current_time_ms,
        )
        assert result == expected
        assert reason == expected_reason

        message = {
            "current_time_ms": int(current_time_ms),
            "message": get_filename(signed_registration),
            "expected": result,
        }
        if reason is not None:
            message["reason"] = reason
        messages.append(message)

    yield "messages", "meta", messages


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
@always_bls
def test_gossip_pq_key_registration__valid(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    yield from run_pq_key_registration_gossip(spec, state, [(signed_registration, "valid", None)])


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
@always_bls
def test_gossip_pq_key_registration__valid_change_after_delay(spec, state):
    register_pq_keys(spec, state, 0, generation=0)
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, generation=1
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "valid", None)],
        epoch=spec.MIN_PQ_KEY_CHANGE_DELAY,
    )


@with_eip8450_and_later
@spec_configured_state_test({"EIP8450_FORK_EPOCH": 1}, activate_at_genesis=True)
def test_gossip_pq_key_registration__ignore_pre_fork(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "ignore", "current epoch is pre-eip8450")],
    )


@with_eip8450_and_later
@spec_configured_state_test({"EIP8450_FORK_EPOCH": 1}, activate_at_genesis=True)
def test_gossip_pq_key_registration__ignore_pre_fork_head_state(spec, state):
    # The clock has reached the fork epoch, but no block of the fork epoch has
    # been imported, so the head state has not been upgraded
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    assert spec.get_current_epoch(state) < spec.config.EIP8450_FORK_EPOCH
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "ignore", "head state is pre-eip8450")],
        epoch=spec.config.EIP8450_FORK_EPOCH,
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
def test_gossip_pq_key_registration__reject_unsupported_version(spec, state):
    public_keys = get_pq_public_keys(spec, 0)
    public_keys.version = spec.PQ_KEYS_VERSION_UNSET
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, public_keys=public_keys
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "unsupported post-quantum keys version")],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
def test_gossip_pq_key_registration__reject_validator_index_out_of_range(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    signed_registration.message.validator_index = len(state.validators)
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "validator index out of range")],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
def test_gossip_pq_key_registration__reject_exit_initiated(spec, state):
    spec.initiate_validator_exit(state, 0)
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "validator has initiated an exit")],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
@always_bls
def test_gossip_pq_key_registration__ignore_already_seen(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    # A different registration for the same validator and change epoch
    other_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, generation=1
    )
    reason = "already seen post-quantum key registration for this pair"
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [
            (signed_registration, "valid", None),
            (signed_registration, "ignore", reason),
            (other_registration, "ignore", reason),
        ],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
@always_bls
def test_gossip_pq_key_registration__invalid_does_not_mark_seen(spec, state):
    invalid_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, privkey=privkeys[1]
    )
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [
            (invalid_registration, "reject", "invalid post-quantum key registration signature"),
            (signed_registration, "valid", None),
        ],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
def test_gossip_pq_key_registration__reject_previous_change_epoch_mismatch(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, previous_change_epoch=spec.Epoch(1)
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "previous change epoch does not match")],
        epoch=1,
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
def test_gossip_pq_key_registration__ignore_change_before_delay(spec, state):
    register_pq_keys(spec, state, 0, generation=0)
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, generation=1
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "ignore", "post-quantum key change delay has not passed")],
        epoch=spec.MIN_PQ_KEY_CHANGE_DELAY - 1,
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
@always_bls
def test_gossip_pq_key_registration__reject_invalid_signature(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, privkey=privkeys[1]
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "invalid post-quantum key registration signature")],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
def test_gossip_pq_key_registration__reject_key_in_use(spec, state):
    owner_keys = register_pq_keys(spec, state, 0, generation=0)
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=1,
        public_keys=owner_keys,
        xmss_secret_key=get_xmss_secret_key(0, generation=0),
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "leanXMSS key is registered by another validator")],
    )


@with_eip8450_and_later
@spec_configured_state_test({}, activate_at_genesis=True)
@always_bls
def test_gossip_pq_key_registration__reject_invalid_possession(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=0,
        xmss_secret_key=get_xmss_secret_key(0, generation=1),
    )
    yield from run_pq_key_registration_gossip(
        spec,
        state,
        [(signed_registration, "reject", "invalid proof of possession")],
    )
