from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8450_and_later,
)
from eth_consensus_specs.test.helpers.eip8450.pq_keys import (
    get_pq_public_keys,
    get_signed_pq_key_registration,
    get_xmss_secret_key,
    register_pq_keys,
    sign_pq_possession_at,
)
from eth_consensus_specs.test.helpers.keys import privkeys


def run_pq_key_registration_processing(spec, state, signed_registration, valid=True):
    """
    Run ``process_pq_key_registration``, yielding:
      - pre-state ('pre')
      - registration ('pq_key_registration')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state

    yield "pq_key_registration", signed_registration

    # If the registration is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_pq_key_registration(state, signed_registration))
        yield "post", None
        return

    spec.process_pq_key_registration(state, signed_registration)

    registration = signed_registration.message
    index = registration.validator_index
    assert state.pq_public_keys[index] == registration.public_keys
    assert state.pq_key_change_epochs[index] == spec.get_current_epoch(state)
    assert spec.is_pq_registered(state, index)

    yield "post", state


def advance_epochs(spec, state, epochs):
    """
    Move ``state`` forward by ``epochs`` epochs without processing them.
    """
    state.slot += spec.Uint64(epochs) * spec.SLOTS_PER_EPOCH


#
# Valid registrations
#


@with_eip8450_and_later
@spec_state_test
def test_success_first_registration(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_last_validator(spec, state):
    validator_index = len(state.validators) - 1
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_first_registration_after_genesis_epoch(spec, state):
    advance_epochs(spec, state, 3)
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    assert signed_registration.message.previous_change_epoch == spec.FAR_FUTURE_EPOCH
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_not_yet_active_validator(spec, state):
    # A validator registers once it has an index, which can be before activation
    validator_index = 1
    state.validators[validator_index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_change_at_delay(spec, state):
    validator_index = 0
    register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, generation=1
    )
    assert signed_registration.message.previous_change_epoch == spec.GENESIS_EPOCH
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_change_after_delay(spec, state):
    validator_index = 0
    advance_epochs(spec, state, 2)
    register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY + 1)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, generation=1
    )
    assert signed_registration.message.previous_change_epoch == 2
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_change_vrf_root_only(spec, state):
    # The validator's own leanXMSS key does not count as in use
    validator_index = 0
    old_keys = register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, generation=0, vrf_generation=1
    )
    new_keys = signed_registration.message.public_keys
    assert new_keys.xmss_public_key == old_keys.xmss_public_key
    assert new_keys.vrf_root != old_keys.vrf_root
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_reregister_same_keys(spec, state):
    validator_index = 0
    old_keys = register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, generation=0
    )
    assert signed_registration.message.public_keys == old_keys
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_key_freed_by_owner_change(spec, state):
    owner_index, registrant_index = 0, 1
    freed_keys = register_pq_keys(spec, state, owner_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    # The owner moves to a new key, which frees its old one
    owner_change = get_signed_pq_key_registration(
        spec, state, validator_index=owner_index, generation=1
    )
    spec.process_pq_key_registration(state, owner_change)

    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=registrant_index,
        public_keys=freed_keys,
        xmss_secret_key=get_xmss_secret_key(owner_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_same_vrf_root_as_other_validator(spec, state):
    # VRF roots are not required to be unique
    other_keys = register_pq_keys(spec, state, 1, generation=0)

    public_keys = get_pq_public_keys(spec, 0)
    public_keys.vrf_root = other_keys.vrf_root
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, public_keys=public_keys
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


#
# Invalid registrations
#


@with_eip8450_and_later
@spec_state_test
def test_invalid_validator_index_out_of_range(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    signed_registration.message.validator_index = len(state.validators)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_exit_initiated(spec, state):
    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].exit_epoch != spec.FAR_FUTURE_EPOCH

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_previous_change_epoch_unregistered(spec, state):
    advance_epochs(spec, state, 1)
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, previous_change_epoch=spec.Epoch(1)
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_previous_change_epoch_genesis_for_unregistered(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, previous_change_epoch=spec.GENESIS_EPOCH
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_previous_change_epoch_registered(spec, state):
    validator_index = 0
    advance_epochs(spec, state, 1)
    register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=validator_index,
        generation=1,
        previous_change_epoch=spec.FAR_FUTURE_EPOCH,
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_replayed_registration(spec, state):
    validator_index = 0
    advance_epochs(spec, state, 1)
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index
    )
    spec.process_pq_key_registration(state, signed_registration)

    # Once applied, the registration no longer names the validator's last change
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY + 1)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_replayed_registration_applied_in_genesis_epoch(spec, state):
    # A change in the genesis epoch stores ``GENESIS_EPOCH``, which differs from
    # the ``FAR_FUTURE_EPOCH`` that the registration names, so it cannot apply
    # again
    validator_index = 0
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index
    )
    spec.process_pq_key_registration(state, signed_registration)
    assert state.pq_key_change_epochs[validator_index] == spec.GENESIS_EPOCH

    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_change_before_delay(spec, state):
    validator_index = 0
    register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY - 1)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, generation=1
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_change_in_same_epoch(spec, state):
    validator_index = 0
    first = get_signed_pq_key_registration(spec, state, validator_index=validator_index)
    spec.process_pq_key_registration(state, first)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, generation=1
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_bls_signature(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=0, privkey=privkeys[1]
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_bls_signature_fork_domain(spec, state):
    # The registration domain is fork-agnostic, so a signature over the current
    # fork's domain is invalid
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    domain = spec.get_domain(state, spec.DOMAIN_PQ_KEY_REGISTRATION)
    signing_root = spec.compute_signing_root(signed_registration.message, domain)
    signed_registration.signature = spec.bls.Sign(privkeys[0], signing_root)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_key_in_use_by_other_validator(spec, state):
    owner_index, registrant_index = 0, 1
    owner_keys = register_pq_keys(spec, state, owner_index, generation=0)

    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=registrant_index,
        public_keys=owner_keys,
        xmss_secret_key=get_xmss_secret_key(owner_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_key_in_use_with_different_vrf_root(spec, state):
    owner_index, registrant_index = 0, 1
    owner_keys = register_pq_keys(spec, state, owner_index, generation=0)

    public_keys = get_pq_public_keys(spec, registrant_index)
    public_keys.xmss_public_key = owner_keys.xmss_public_key
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=registrant_index,
        public_keys=public_keys,
        xmss_secret_key=get_xmss_secret_key(owner_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_possession_by_other_key(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        validator_index=0,
        xmss_secret_key=get_xmss_secret_key(0, generation=1),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_possession_for_other_validator(spec, state):
    # A proof made for another validator's BLS public key cannot be reused
    validator_index, other_index = 0, 1
    possession = spec.get_pq_possession_proof(
        state,
        state.validators[other_index].pubkey,
        get_xmss_secret_key(validator_index),
    )
    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, possession=possession
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_possession_wrong_leaf_index(spec, state):
    # The proof is a valid signature of the right message, at the wrong leaf
    validator_index = 0
    xmss_secret_key = get_xmss_secret_key(validator_index)
    possession = sign_pq_possession_at(
        spec,
        state,
        state.validators[validator_index].pubkey,
        xmss_secret_key,
        spec.PQ_POSSESSION_XMSS_INDEX + 1,
    )
    public_keys = get_pq_public_keys(spec, validator_index)
    signing_root = spec.get_pq_possession_signing_root(
        state, state.validators[validator_index].pubkey, public_keys.xmss_public_key
    )
    assert spec.xmss.Verify(public_keys.xmss_public_key, signing_root, possession)

    signed_registration = get_signed_pq_key_registration(
        spec, state, validator_index=validator_index, possession=possession
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_possession_corrupted(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, validator_index=0)
    possession = bytearray(signed_registration.possession)
    possession[-1] ^= 0x01
    signed_registration.possession = spec.XMSSSignature(possession)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)
