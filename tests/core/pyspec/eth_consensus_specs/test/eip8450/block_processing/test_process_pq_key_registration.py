from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    never_bls,
    spec_state_test,
    with_eip8450_and_later,
)
from eth_consensus_specs.test.helpers.eip8450.pq_keys import (
    activate_builders,
    builder_registry_index,
    get_possession_signing_root,
    get_pq_entry,
    get_pq_key_material,
    get_signed_pq_key_registration,
    get_xmss_secret_key,
    is_registered,
    register_pq_keys,
    sign_pq_possession_at,
)
from eth_consensus_specs.test.helpers.keys import builder_pubkeys, privkeys


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
    index = registration.index
    assert get_pq_entry(spec, state, index) == (
        registration.key_material,
        spec.get_current_epoch(state),
    )
    assert is_registered(spec, state, index)

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
    # Every other entry holds the all-zero key, which does not block another key
    assert all(entry == spec.PQKeyMaterial() for entry in state.post_quantum_key_material)
    assert all(entry == spec.PQKeyMaterial() for entry in state.builder_post_quantum_key_material)
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_last_validator(spec, state):
    validator_index = len(state.validators) - 1
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_first_registration_after_genesis_epoch(spec, state):
    advance_epochs(spec, state, 3)
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
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

    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_change_at_delay(spec, state):
    validator_index = 0
    register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=1
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
        spec, state, index=validator_index, generation=1
    )
    assert signed_registration.message.previous_change_epoch == 2
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_change_keeping_vrf_root(spec, state):
    validator_index = 0
    old_keys = register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=1, vrf_generation=0
    )
    new_keys = signed_registration.message.key_material
    assert new_keys.xmss_public_key != old_keys.xmss_public_key
    assert new_keys.vrf_root == old_keys.vrf_root
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
@never_bls
def test_invalid_all_zero_key(spec, state):
    # The all-zero key marks an entry without keys, so it cannot be registered.
    # Without BLS, the proof of possession passes, so only the all-zero check
    # rejects it.
    key_material = get_pq_key_material(spec, 0)
    key_material.xmss_public_key = spec.XMSSPublicKey()
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=0, key_material=key_material
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_success_key_released_by_other_validator(spec, state):
    """
    Consensus accepts a key that another validator held and released through a
    change, since earlier keys are not recorded. Honest signers never do this:
    it needs a proof of a different message at leaf ``PQ_POSSESSION_XMSS_INDEX``.
    """
    owner_index, registrant_index = 0, 1
    released_keys = register_pq_keys(spec, state, owner_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    # The owner moves to a new key, which releases its old one
    owner_change = get_signed_pq_key_registration(spec, state, index=owner_index, generation=1)
    spec.process_pq_key_registration(state, owner_change)

    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=registrant_index,
        key_material=released_keys,
        xmss_secret_key=get_xmss_secret_key(owner_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_return_to_earlier_own_key(spec, state):
    """
    Consensus accepts a validator returning to a key it held before, since
    earlier keys are not recorded. It needs either a second proof at leaf
    ``PQ_POSSESSION_XMSS_INDEX`` or the stored first one, and honest signers
    never do it.
    """
    validator_index = 0
    earlier_keys = register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    change = get_signed_pq_key_registration(spec, state, index=validator_index, generation=1)
    spec.process_pq_key_registration(state, change)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=0
    )
    assert signed_registration.message.key_material == earlier_keys
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_same_vrf_root_as_other_validator(spec, state):
    # VRF roots are not required to be unique
    other_keys = register_pq_keys(spec, state, 1, generation=0)

    key_material = get_pq_key_material(spec, 0)
    key_material.vrf_root = other_keys.vrf_root
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=0, key_material=key_material
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_key_released_by_validator_to_builder_sharing_pubkey(spec, state):
    """
    A validator and a builder may share a BLS public key. Once the validator
    releases a key through a change, consensus accepts the builder registering
    it with the identical proof bytes. Honest signers never do this.
    """
    activate_builders(spec, state)
    validator_index = 0
    builder_index = 0
    state.builders[builder_index].pubkey = state.validators[validator_index].pubkey

    validator_registration = get_signed_pq_key_registration(spec, state, index=validator_index)
    spec.process_pq_key_registration(state, validator_registration)
    released_keys = validator_registration.message.key_material
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)
    validator_change = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=1
    )
    spec.process_pq_key_registration(state, validator_change)

    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=builder_registry_index(spec, builder_index),
        key_material=spec.PQKeyMaterial(xmss_public_key=released_keys.xmss_public_key),
        privkey=privkeys[validator_index],
        possession=validator_registration.possession,
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


#
# Invalid registrations
#


@with_eip8450_and_later
@spec_state_test
def test_invalid_validator_index_out_of_range(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
    signed_registration.message.index = len(state.validators)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_exit_initiated(spec, state):
    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].exit_epoch != spec.FAR_FUTURE_EPOCH

    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_previous_change_epoch_unregistered(spec, state):
    advance_epochs(spec, state, 1)
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=0, previous_change_epoch=spec.Epoch(1)
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_previous_change_epoch_genesis_for_unregistered(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=0, previous_change_epoch=spec.GENESIS_EPOCH
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
        index=validator_index,
        generation=1,
        previous_change_epoch=spec.FAR_FUTURE_EPOCH,
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_replayed_registration(spec, state):
    validator_index = 0
    advance_epochs(spec, state, 1)
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)
    spec.process_pq_key_registration(state, signed_registration)

    # Once applied, the registration no longer names the validator's last change
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY + 1)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_replayed_registration_after_key_released(spec, state):
    # A later change released the replayed registration's key, so only the
    # previous change epoch rejects the replay
    validator_index = 0
    advance_epochs(spec, state, 1)
    first = get_signed_pq_key_registration(spec, state, index=validator_index, generation=0)
    spec.process_pq_key_registration(state, first)

    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)
    change = get_signed_pq_key_registration(spec, state, index=validator_index, generation=1)
    spec.process_pq_key_registration(state, change)

    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)
    assert not spec.is_pq_public_key_in_use(state, first.message.key_material.xmss_public_key)
    assert first.message.previous_change_epoch != state.post_quantum_key_change_epochs[0]
    yield from run_pq_key_registration_processing(spec, state, first, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_replayed_registration_applied_in_genesis_epoch(spec, state):
    # A change in the genesis epoch stores ``GENESIS_EPOCH``, which differs from
    # the ``FAR_FUTURE_EPOCH`` that the registration names, so it cannot apply
    # again
    validator_index = 0
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)
    spec.process_pq_key_registration(state, signed_registration)
    assert state.post_quantum_key_change_epochs[validator_index] == spec.GENESIS_EPOCH

    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_change_before_delay(spec, state):
    validator_index = 0
    register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY - 1)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=1
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_change_in_same_epoch(spec, state):
    validator_index = 0
    first = get_signed_pq_key_registration(spec, state, index=validator_index)
    spec.process_pq_key_registration(state, first)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=1
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


def sign_registration_with_domain(spec, registration, privkey, domain):
    signing_root = spec.compute_signing_root(registration, domain)
    return spec.bls.Sign(privkey, signing_root)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_bls_signature(spec, state):
    # A valid signature by the registrant's key, of another message
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
    other_message = signed_registration.message.copy()
    other_message.previous_change_epoch = spec.Epoch(0)
    domain = spec.compute_domain(
        spec.DOMAIN_PQ_KEY_REGISTRATION,
        spec.config.GENESIS_FORK_VERSION,
        state.genesis_validators_root,
    )
    signed_registration.signature = sign_registration_with_domain(
        spec, other_message, privkeys[0], domain
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_bls_signature_by_other_validator_key(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, index=0, privkey=privkeys[1])
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_bls_signature_wrong_domain_type(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
    domain = spec.compute_domain(
        spec.DOMAIN_PQ_KEY_POSSESSION,
        spec.config.GENESIS_FORK_VERSION,
        state.genesis_validators_root,
    )
    signed_registration.signature = sign_registration_with_domain(
        spec, signed_registration.message, privkeys[0], domain
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_bls_signature_current_fork_version(spec, state):
    # The registration domain uses the genesis fork version, so a signature over
    # the current fork version's domain is invalid
    assert state.fork.current_version != spec.config.GENESIS_FORK_VERSION
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
    domain = spec.get_domain(state, spec.DOMAIN_PQ_KEY_REGISTRATION)
    signed_registration.signature = sign_registration_with_domain(
        spec, signed_registration.message, privkeys[0], domain
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_key_in_use_by_other_validator(spec, state):
    owner_index, registrant_index = 0, 1
    owner_keys = register_pq_keys(spec, state, owner_index, generation=0)

    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=registrant_index,
        key_material=owner_keys,
        xmss_secret_key=get_xmss_secret_key(owner_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_key_in_use_with_different_vrf_root(spec, state):
    owner_index, registrant_index = 0, 1
    owner_keys = register_pq_keys(spec, state, owner_index, generation=0)

    key_material = get_pq_key_material(spec, registrant_index)
    key_material.xmss_public_key = owner_keys.xmss_public_key
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=registrant_index,
        key_material=key_material,
        xmss_secret_key=get_xmss_secret_key(owner_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_reregister_own_keys(spec, state):
    # The validator's own current key counts as in use
    validator_index = 0
    old_keys = register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=0
    )
    assert signed_registration.message.key_material == old_keys
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_change_vrf_root_only(spec, state):
    # Changing the VRF root requires a new leanXMSS key
    validator_index = 0
    old_keys = register_pq_keys(spec, state, validator_index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, generation=0, vrf_generation=1
    )
    new_keys = signed_registration.message.key_material
    assert new_keys.xmss_public_key == old_keys.xmss_public_key
    assert new_keys.vrf_root != old_keys.vrf_root
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_possession_by_other_key(spec, state):
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=0,
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
        spec, state, index=validator_index, possession=possession
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
    key_material = get_pq_key_material(spec, validator_index)
    signing_root = get_possession_signing_root(
        spec, state, state.validators[validator_index].pubkey, key_material.xmss_public_key
    )
    assert spec.xmss.Verify(key_material.xmss_public_key, signing_root, possession)

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=validator_index, possession=possession
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_possession_corrupted(spec, state):
    signed_registration = get_signed_pq_key_registration(spec, state, index=0)
    possession = bytearray(signed_registration.possession)
    possession[-1] ^= 0x01
    signed_registration.possession = spec.XMSSSignature(possession)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


#
# Builders
#


def withdraw_builder(spec, state, builder_index):
    """
    Exit and fully withdraw the builder, so that its index can be reassigned.
    """
    builder = state.builders[builder_index]
    builder.withdrawable_epoch = spec.get_current_epoch(state)
    builder.balance = 0


def add_builder_at_reused_index(spec, state, builder_index, pubkey):
    """
    Reassign the withdrawn ``builder_index`` to a builder with ``pubkey``, and
    finalize its deposit epoch so that it is active.
    """
    assert spec.get_index_for_new_builder(state) == builder_index
    spec.add_builder_to_registry(
        state,
        pubkey,
        spec.Uint8(0),
        spec.ExecutionAddress(b"\x42" * 20),
        spec.MIN_DEPOSIT_AMOUNT,
        state.slot,
    )
    deposit_epoch = spec.get_current_epoch(state)
    assert state.builders[builder_index].deposit_epoch == deposit_epoch
    assert state.builder_post_quantum_key_material[builder_index] == spec.PQKeyMaterial()
    assert state.builder_post_quantum_key_change_epochs[builder_index] == deposit_epoch
    advance_epochs(spec, state, 2)
    state.finalized_checkpoint.epoch = deposit_epoch + 1
    assert spec.is_active_builder(state, builder_index)


@with_eip8450_and_later
@spec_state_test
def test_success_builder_first_registration(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    signed_registration = get_signed_pq_key_registration(spec, state, index=index)
    assert signed_registration.message.key_material.vrf_root == spec.VRFRoot()
    assert signed_registration.message.previous_change_epoch == state.builders[0].deposit_epoch
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_builder_first_registration_within_change_delay_of_deposit(spec, state):
    # The change delay applies only to a builder that holds a key, so a first
    # registration soon after the deposit epoch is accepted
    activate_builders(spec, state)
    withdraw_builder(spec, state, 0)
    add_builder_at_reused_index(spec, state, 0, builder_pubkeys[len(state.builders)])
    deposit_epoch = state.builders[0].deposit_epoch
    assert deposit_epoch > spec.GENESIS_EPOCH
    assert spec.get_current_epoch(state) < deposit_epoch + spec.MIN_PQ_KEY_CHANGE_DELAY

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=builder_registry_index(spec, 0)
    )
    assert signed_registration.message.previous_change_epoch == deposit_epoch
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_builder_last_builder(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, len(state.builders) - 1)
    signed_registration = get_signed_pq_key_registration(spec, state, index=index)
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_builder_change_after_delay(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    register_pq_keys(spec, state, index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(spec, state, index=index, generation=1)
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_success_builder_registration_after_index_reuse(spec, state):
    activate_builders(spec, state)
    register_pq_keys(spec, state, builder_registry_index(spec, 0), generation=0)
    withdraw_builder(spec, state, 0)
    add_builder_at_reused_index(spec, state, 0, builder_pubkeys[len(state.builders)])

    signed_registration = get_signed_pq_key_registration(
        spec, state, index=builder_registry_index(spec, 0), generation=1
    )
    assert signed_registration.message.previous_change_epoch == state.builders[0].deposit_epoch
    yield from run_pq_key_registration_processing(spec, state, signed_registration)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_index_out_of_range(spec, state):
    activate_builders(spec, state)
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=builder_registry_index(spec, 0)
    )
    signed_registration.message.index = builder_registry_index(spec, len(state.builders))
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_not_yet_active(spec, state):
    # The builder's deposit epoch is not yet finalized
    assert state.finalized_checkpoint.epoch <= state.builders[0].deposit_epoch
    index = builder_registry_index(spec, 0)
    assert not spec.is_active_builder(state, 0)
    signed_registration = get_signed_pq_key_registration(spec, state, index=index)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_exit_initiated(spec, state):
    activate_builders(spec, state)
    spec.initiate_builder_exit(state, 0)
    assert not spec.is_active_builder(state, 0)
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=builder_registry_index(spec, 0)
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_nonzero_vrf_root(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    key_material = get_pq_key_material(spec, index)
    key_material.vrf_root = spec.VRFRoot(b"\x01" * 32)
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=index, key_material=key_material
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_previous_change_epoch_far_future(spec, state):
    # A builder that has never registered names its deposit epoch, not the
    # validator marker
    activate_builders(spec, state)
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=builder_registry_index(spec, 0),
        previous_change_epoch=spec.FAR_FUTURE_EPOCH,
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_change_before_delay(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    register_pq_keys(spec, state, index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY - 1)

    signed_registration = get_signed_pq_key_registration(spec, state, index=index, generation=1)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@always_bls
def test_invalid_builder_signed_by_validator_key(spec, state):
    activate_builders(spec, state)
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=builder_registry_index(spec, 0), privkey=privkeys[0]
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_key_in_use_by_validator(spec, state):
    activate_builders(spec, state)
    validator_keys = register_pq_keys(spec, state, 0, generation=0)

    key_material = spec.PQKeyMaterial(xmss_public_key=validator_keys.xmss_public_key)
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=builder_registry_index(spec, 0),
        key_material=key_material,
        xmss_secret_key=get_xmss_secret_key(0, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_validator_key_in_use_by_builder(spec, state):
    activate_builders(spec, state)
    builder_index = builder_registry_index(spec, 0)
    builder_keys = register_pq_keys(spec, state, builder_index, generation=0)

    key_material = get_pq_key_material(spec, 0)
    key_material.xmss_public_key = builder_keys.xmss_public_key
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=0,
        key_material=key_material,
        xmss_secret_key=get_xmss_secret_key(builder_index, generation=0),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_builder_reregister_own_key(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    register_pq_keys(spec, state, index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)

    signed_registration = get_signed_pq_key_registration(spec, state, index=index, generation=0)
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
@never_bls
def test_invalid_builder_all_zero_key(spec, state):
    # Without BLS, the proof of possession passes, so only the all-zero check
    # rejects it
    activate_builders(spec, state)
    signed_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=builder_registry_index(spec, 0),
        key_material=spec.PQKeyMaterial(),
    )
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_earlier_builder_registration_after_index_reuse(spec, state):
    # A first registration signed by the earlier builder names its deposit epoch
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    signed_registration = get_signed_pq_key_registration(spec, state, index=index)

    withdraw_builder(spec, state, 0)
    add_builder_at_reused_index(spec, state, 0, builder_pubkeys[len(state.builders)])
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_earlier_builder_registration_after_same_key_reenters(spec, state):
    # A change signed by the earlier builder names its last change epoch. A
    # deposit for a key still in the registry is a top-up, so the same BLS key
    # returns to the index only after another builder has held it. Only the
    # epoch rejects the earlier registration.
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    register_pq_keys(spec, state, index, generation=0)
    advance_epochs(spec, state, spec.MIN_PQ_KEY_CHANGE_DELAY)
    signed_registration = get_signed_pq_key_registration(spec, state, index=index, generation=1)
    earlier_pubkey = state.builders[0].pubkey
    assert earlier_pubkey == builder_pubkeys[0]

    withdraw_builder(spec, state, 0)
    add_builder_at_reused_index(spec, state, 0, builder_pubkeys[len(state.builders)])
    withdraw_builder(spec, state, 0)
    add_builder_at_reused_index(spec, state, 0, earlier_pubkey)
    assert not is_registered(spec, state, index)
    assert signed_registration.message.previous_change_epoch != state.builders[0].deposit_epoch
    yield from run_pq_key_registration_processing(spec, state, signed_registration, valid=False)
