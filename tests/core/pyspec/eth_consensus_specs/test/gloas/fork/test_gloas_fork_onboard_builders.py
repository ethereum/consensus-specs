from eth_consensus_specs.test.context import (
    always_bls,
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    FULU,
    GLOAS,
)
from eth_consensus_specs.test.helpers.deposits import build_deposit_data
from eth_consensus_specs.test.helpers.gloas.fork import (
    GLOAS_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth_consensus_specs.test.helpers.keys import (
    builder_pubkey_to_privkey,
    builder_pubkeys,
    privkeys,
    pubkeys,
)
from eth_consensus_specs.test.utils import with_meta_tags


def get_builder_withdrawal_credentials(spec, pubkey):
    """Create builder withdrawal credentials from a pubkey."""
    return spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + spec.sha256(pubkey)[12:]


def create_pending_deposit_for_builder(spec, pubkey, amount, signed=True):
    """Create a pending deposit with builder withdrawal credentials."""
    privkey = builder_pubkey_to_privkey[pubkey]
    withdrawal_credentials = get_builder_withdrawal_credentials(spec, pubkey)

    deposit_data = build_deposit_data(
        spec,
        pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed=signed,
    )

    return spec.PendingDeposit(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        slot=spec.GENESIS_SLOT,
    )


def create_pending_deposit_for_validator(spec, validator_index, amount):
    """Create a pending deposit with validator withdrawal credentials."""
    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    # ETH1 withdrawal credentials
    withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20

    deposit_data = build_deposit_data(
        spec,
        pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed=True,
    )

    return spec.PendingDeposit(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        slot=spec.GENESIS_SLOT,
    )


def create_pending_deposit_for_unregistered_validator(spec, pubkey, amount, signed=True):
    """
    Create a pending deposit with compounding validator credentials for a pubkey
    that is not already in the validator registry.
    """
    privkey = builder_pubkey_to_privkey[pubkey]
    withdrawal_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20

    if signed:
        deposit_data = build_deposit_data(
            spec,
            pubkey,
            privkey,
            amount,
            withdrawal_credentials,
            signed=True,
        )
        signature = deposit_data.signature
    else:
        signature = spec.bls.G2_POINT_AT_INFINITY

    return spec.PendingDeposit(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        signature=signature,
        slot=spec.GENESIS_SLOT,
    )


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_no_pending_deposits(spec, phases, state):
    """
    Test fork with no pending deposits - no builders should be created.
    """
    # Ensure no pending deposits
    state.pending_deposits = spec.PendingDeposits()

    post_spec = phases[GLOAS]
    post_state = yield from run_fork_test(post_spec, state)

    # No builders should be created
    assert len(post_state.builders) == 0
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_single_builder_deposit(spec, phases, state):
    """
    Test fork with a single pending deposit with builder credentials.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create a pending deposit with builder credentials
    builder_pubkey = builder_pubkeys[0]
    pending_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)
    state.pending_deposits = spec.PendingDeposits.of(pending_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # One builder should be created
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey
    assert post_state.builders[0].balance == amount

    # Pending deposit should be removed
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_builder_deposit_version(spec, phases, state):
    """
    Test that a builder onboarded at the fork is registered as a payload builder.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create a pending deposit with builder credentials
    builder_pubkey = builder_pubkeys[0]
    pending_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)
    state.pending_deposits = spec.PendingDeposits.of(pending_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # The onboarded builder is registered with the payload builder version
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey
    assert post_state.builders[0].version == post_spec.PAYLOAD_BUILDER_VERSION


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_builder_deposit_uses_deposit_slot_epoch(spec, phases, state):
    """
    Test fork uses the deposit's slot epoch when onboarding builders.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Set state slot to a later epoch than the deposit slot
    state.slot = post_spec.SLOTS_PER_EPOCH * 2

    builder_pubkey = builder_pubkeys[0]
    pending_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)
    pending_deposit.slot = state.slot - 1
    state.pending_deposits = spec.PendingDeposits.of(pending_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.builders) == 1
    builder = post_state.builders[0]
    assert builder.deposit_epoch == post_spec.compute_epoch_at_slot(pending_deposit.slot)
    assert builder.deposit_epoch != post_spec.get_current_epoch(post_state)
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_multiple_builder_deposits(spec, phases, state):
    """
    Test fork with multiple pending deposits with builder credentials.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create multiple pending deposits with builder credentials
    pending_deposits = spec.PendingDeposits()
    for i in range(3):
        builder_pubkey = builder_pubkeys[i]
        pending_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)
        pending_deposits.append(pending_deposit)

    state.pending_deposits = pending_deposits

    post_state = yield from run_fork_test(post_spec, state)

    # Three builders should be created
    assert len(post_state.builders) == 3
    for i in range(3):
        assert post_state.builders[i].pubkey == builder_pubkeys[i]
        assert post_state.builders[i].balance == amount

    # All pending deposits should be removed
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_pending_deposit_for_existing_validator(spec, phases, state):
    """
    Test fork with pending deposit for an existing validator - should stay in queue.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create a pending deposit for an existing validator (top-up)
    validator_pubkey = state.validators[0].pubkey
    withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20

    pending_deposit = spec.PendingDeposit(
        pubkey=validator_pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        signature=spec.bls.G2_POINT_AT_INFINITY,
        slot=spec.GENESIS_SLOT,
    )
    state.pending_deposits = spec.PendingDeposits.of(pending_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # No builders should be created
    assert len(post_state.builders) == 0

    # Pending deposit should remain (for existing validator)
    assert len(post_state.pending_deposits) == 1
    assert post_state.pending_deposits[0].pubkey == validator_pubkey


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_pending_deposit_validator_credentials(spec, phases, state):
    """
    Test fork with pending deposit with validator credentials (not builder) - should stay in queue.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create a pending deposit for a new validator (not builder credentials)
    # Use a pubkey that's not already a validator
    new_validator_index = len(state.validators)
    pending_deposit = create_pending_deposit_for_validator(post_spec, new_validator_index, amount)
    state.pending_deposits = spec.PendingDeposits.of(pending_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # No builders should be created
    assert len(post_state.builders) == 0

    # Pending deposit should remain (for new validator creation later)
    assert len(post_state.pending_deposits) == 1
    assert post_state.pending_deposits[0].pubkey == pubkeys[new_validator_index]


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_mixed_pending_deposits(spec, phases, state):
    """
    Test fork with mixed pending deposits - builder and validator.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create pending deposits:
    # 1. Builder deposit (new builder)
    # 2. Validator deposit for existing validator (top-up)
    # 3. Another builder deposit
    # 4. Validator deposit for new validator

    builder_pubkey_1 = builder_pubkeys[0]
    builder_deposit_1 = create_pending_deposit_for_builder(post_spec, builder_pubkey_1, amount)

    validator_pubkey = state.validators[0].pubkey
    validator_topup = spec.PendingDeposit(
        pubkey=validator_pubkey,
        withdrawal_credentials=spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20,
        amount=amount,
        signature=spec.bls.G2_POINT_AT_INFINITY,
        slot=spec.GENESIS_SLOT,
    )

    builder_pubkey_2 = builder_pubkeys[1]
    builder_deposit_2 = create_pending_deposit_for_builder(post_spec, builder_pubkey_2, amount)

    new_validator_index = len(state.validators)
    new_validator_deposit = create_pending_deposit_for_validator(
        post_spec, new_validator_index, amount
    )

    state.pending_deposits = spec.PendingDeposits.of(
        builder_deposit_1, validator_topup, builder_deposit_2, new_validator_deposit
    )

    post_state = yield from run_fork_test(post_spec, state)

    # Two builders should be created
    assert len(post_state.builders) == 2
    assert post_state.builders[0].pubkey == builder_pubkey_1
    assert post_state.builders[1].pubkey == builder_pubkey_2

    # Two pending deposits should remain (validator top-up and new validator)
    assert len(post_state.pending_deposits) == 2
    assert post_state.pending_deposits[0].pubkey == validator_pubkey
    assert post_state.pending_deposits[1].pubkey == pubkeys[new_validator_index]


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_multiple_deposits_same_builder(spec, phases, state):
    """
    Test fork with multiple deposits for the same builder pubkey.
    First deposit creates the builder, subsequent ones increase balance.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create multiple pending deposits for the same builder
    builder_pubkey = builder_pubkeys[0]
    pending_deposits = spec.PendingDeposits()
    for _ in range(3):
        pending_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)
        pending_deposits.append(pending_deposit)

    state.pending_deposits = pending_deposits

    post_state = yield from run_fork_test(post_spec, state)

    # Only one builder should be created (not three)
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey

    # Balance should be the sum of all deposits
    assert post_state.builders[0].balance == amount * 3

    # All pending deposits should be removed
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_builder_deposit_with_existing_validator_pubkey_builder_creds(spec, phases, state):
    """
    Test fork with builder credentials but for an existing validator pubkey.
    Should stay in pending deposits (not create a builder).
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    # Create a pending deposit with builder credentials but using validator's pubkey
    validator_pubkey = state.validators[0].pubkey
    withdrawal_credentials = get_builder_withdrawal_credentials(post_spec, validator_pubkey)

    pending_deposit = spec.PendingDeposit(
        pubkey=validator_pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        signature=spec.bls.G2_POINT_AT_INFINITY,
        slot=spec.GENESIS_SLOT,
    )
    state.pending_deposits = spec.PendingDeposits.of(pending_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # No builders should be created (pubkey is already a validator)
    assert len(post_state.builders) == 0

    # Pending deposit should remain
    assert len(post_state.pending_deposits) == 1
    assert post_state.pending_deposits[0].pubkey == validator_pubkey


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_builder_deposit_followed_by_non_builder_credentials(spec, phases, state):
    """
    Test fork with two deposits for the same builder pubkey:
    - First deposit has builder credentials
    - Second deposit has non-builder credentials
    Both should be applied to the builder.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    builder_pubkey = builder_pubkeys[0]
    privkey = builder_pubkey_to_privkey[builder_pubkey]

    # First deposit: builder credentials
    builder_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)

    # Second deposit: compounding credentials (0x02) for the same pubkey
    compounding_withdrawal_credentials = (
        post_spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20
    )
    deposit_data = build_deposit_data(
        post_spec,
        builder_pubkey,
        privkey,
        amount,
        compounding_withdrawal_credentials,
        signed=True,
    )
    non_builder_deposit = post_spec.PendingDeposit(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        slot=post_spec.GENESIS_SLOT,
    )

    state.pending_deposits = spec.PendingDeposits.of(builder_deposit, non_builder_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # One builder should be created
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey

    # Balance should be the sum of both deposits
    assert post_state.builders[0].balance == amount * 2

    # Both pending deposits should be removed (applied to builder)
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_validator_deposit_followed_by_builder_credentials(spec, phases, state):
    """
    Test fork with two deposits for the same pubkey:
    - First deposit has validator credentials
    - Second deposit has builder credentials
    Both deposits should stay in pending (no builder created).
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    builder_pubkey = builder_pubkeys[0]
    privkey = builder_pubkey_to_privkey[builder_pubkey]

    # First deposit: compounding credentials (0x02)
    compounding_withdrawal_credentials = (
        post_spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20
    )
    deposit_data_validator = build_deposit_data(
        post_spec,
        builder_pubkey,
        privkey,
        amount,
        compounding_withdrawal_credentials,
        signed=True,
    )
    validator_deposit = post_spec.PendingDeposit(
        pubkey=deposit_data_validator.pubkey,
        withdrawal_credentials=deposit_data_validator.withdrawal_credentials,
        amount=deposit_data_validator.amount,
        signature=deposit_data_validator.signature,
        slot=post_spec.GENESIS_SLOT,
    )

    # Second deposit: builder credentials for the same pubkey
    builder_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)

    state.pending_deposits = spec.PendingDeposits.of(validator_deposit, builder_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # No builder should be created (first valid deposit was for validator)
    assert len(post_state.builders) == 0

    # Both deposits should remain in pending
    assert len(post_state.pending_deposits) == 2
    assert post_state.pending_deposits[0].pubkey == builder_pubkey
    assert (
        post_state.pending_deposits[0].withdrawal_credentials == compounding_withdrawal_credentials
    )
    assert post_state.pending_deposits[1].pubkey == builder_pubkey
    assert (
        post_state.pending_deposits[1].withdrawal_credentials
        == builder_deposit.withdrawal_credentials
    )


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_invalid_validator_deposit_followed_by_builder_credentials(spec, phases, state):
    """
    Test fork with two deposits for the same pubkey:
    - First deposit has validator credentials but INVALID signature
    - Second deposit has builder credentials with valid signature
    The invalid validator deposit should not block the builder deposit.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    builder_pubkey = builder_pubkeys[0]

    # First deposit: compounding credentials (0x02) with INVALID signature
    compounding_withdrawal_credentials = (
        post_spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20
    )
    invalid_validator_deposit = post_spec.PendingDeposit(
        pubkey=builder_pubkey,
        withdrawal_credentials=compounding_withdrawal_credentials,
        amount=amount,
        signature=post_spec.bls.G2_POINT_AT_INFINITY,  # Invalid signature
        slot=post_spec.GENESIS_SLOT,
    )

    # Second deposit: builder credentials with valid signature
    builder_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)

    state.pending_deposits = spec.PendingDeposits.of(invalid_validator_deposit, builder_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # Builder should be created (invalid validator deposit doesn't claim the pubkey)
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey
    assert post_state.builders[0].balance == amount

    # Invalid validator deposit stays in pending queue
    assert len(post_state.pending_deposits) == 1
    assert post_state.pending_deposits[0].pubkey == builder_pubkey
    assert (
        post_state.pending_deposits[0].withdrawal_credentials == compounding_withdrawal_credentials
    )


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_invalid_builder_deposit_followed_by_valid_builder_deposit(spec, phases, state):
    """
    Test fork with two builder deposits for the same pubkey:
    - First deposit has builder credentials but INVALID signature
    - Second deposit has builder credentials with valid signature
    The valid second deposit should create the builder.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    builder_pubkey = builder_pubkeys[0]
    builder_withdrawal_credentials = get_builder_withdrawal_credentials(post_spec, builder_pubkey)

    # First deposit: builder credentials with INVALID signature
    invalid_builder_deposit = post_spec.PendingDeposit(
        pubkey=builder_pubkey,
        withdrawal_credentials=builder_withdrawal_credentials,
        amount=amount,
        signature=post_spec.bls.G2_POINT_AT_INFINITY,  # Invalid signature
        slot=post_spec.GENESIS_SLOT,
    )

    # Second deposit: builder credentials with valid signature
    valid_builder_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)

    state.pending_deposits = spec.PendingDeposits.of(invalid_builder_deposit, valid_builder_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # Builder should be created from the valid second deposit
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey
    # Only the valid deposit amount should be counted
    assert post_state.builders[0].balance == amount

    # No pending deposits should remain
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_valid_builder_deposit_followed_by_invalid_builder_deposit(spec, phases, state):
    """
    Test fork with two builder deposits for the same pubkey:
    - First deposit has builder credentials with valid signature
    - Second deposit has builder credentials but INVALID signature
    The valid first deposit should create the builder, second adds to balance.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT

    builder_pubkey = builder_pubkeys[0]
    builder_withdrawal_credentials = get_builder_withdrawal_credentials(post_spec, builder_pubkey)

    # First deposit: builder credentials with valid signature
    valid_builder_deposit = create_pending_deposit_for_builder(post_spec, builder_pubkey, amount)

    # Second deposit: builder credentials with INVALID signature
    invalid_builder_deposit = post_spec.PendingDeposit(
        pubkey=builder_pubkey,
        withdrawal_credentials=builder_withdrawal_credentials,
        amount=amount,
        signature=post_spec.bls.G2_POINT_AT_INFINITY,  # Invalid signature
        slot=post_spec.GENESIS_SLOT,
    )

    state.pending_deposits = spec.PendingDeposits.of(valid_builder_deposit, invalid_builder_deposit)

    post_state = yield from run_fork_test(post_spec, state)

    # Builder should be created from the valid first deposit
    assert len(post_state.builders) == 1
    assert post_state.builders[0].pubkey == builder_pubkey
    # Both deposits should be applied (second is a top-up, no signature check needed)
    assert post_state.builders[0].balance == amount * 2

    # No pending deposits should remain
    assert len(post_state.pending_deposits) == 0


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
@always_bls
def test_fork_valid_then_invalid_validator_then_builder_deposit(spec, phases, state):
    """
    Test fork with three deposits for the same unregistered pubkey:
    - First deposit has validator credentials with a valid signature
    - Second deposit has validator credentials with an invalid signature
    - Third deposit has builder credentials with a valid signature

    ``is_pending_validator`` is existential: a later invalid signature must not
    erase an earlier valid validator deposit. All three deposits stay pending
    and no builder is created.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT
    pubkey = builder_pubkeys[0]

    valid_validator_deposit = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=True
    )
    invalid_validator_deposit = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=False
    )
    builder_deposit = create_pending_deposit_for_builder(post_spec, pubkey, amount)

    state.pending_deposits = spec.PendingDeposits.of(
        valid_validator_deposit,
        invalid_validator_deposit,
        builder_deposit,
    )

    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.builders) == 0
    assert len(post_state.pending_deposits) == 3
    assert post_state.pending_deposits[0].pubkey == pubkey
    assert (
        post_state.pending_deposits[0].withdrawal_credentials
        == valid_validator_deposit.withdrawal_credentials
    )
    assert post_state.pending_deposits[1].pubkey == pubkey
    assert (
        post_state.pending_deposits[1].withdrawal_credentials
        == invalid_validator_deposit.withdrawal_credentials
    )
    assert post_state.pending_deposits[1].signature == post_spec.bls.G2_POINT_AT_INFINITY
    assert post_state.pending_deposits[2].pubkey == pubkey
    assert (
        post_state.pending_deposits[2].withdrawal_credentials
        == builder_deposit.withdrawal_credentials
    )


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
@always_bls
def test_fork_invalid_then_valid_validator_then_builder_deposit(spec, phases, state):
    """
    Test fork with three deposits for the same unregistered pubkey:
    - First deposit has validator credentials with an invalid signature
    - Second deposit has validator credentials with a valid signature
    - Third deposit has builder credentials with a valid signature

    The later valid validator deposit still claims the pubkey, so all three
    deposits stay pending and no builder is created.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT
    pubkey = builder_pubkeys[0]

    invalid_validator_deposit = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=False
    )
    valid_validator_deposit = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=True
    )
    builder_deposit = create_pending_deposit_for_builder(post_spec, pubkey, amount)

    state.pending_deposits = spec.PendingDeposits.of(
        invalid_validator_deposit,
        valid_validator_deposit,
        builder_deposit,
    )

    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.builders) == 0
    assert len(post_state.pending_deposits) == 3
    assert post_state.pending_deposits[0].pubkey == pubkey
    assert post_state.pending_deposits[0].signature == post_spec.bls.G2_POINT_AT_INFINITY
    assert post_state.pending_deposits[1].pubkey == pubkey
    assert (
        post_state.pending_deposits[1].withdrawal_credentials
        == valid_validator_deposit.withdrawal_credentials
    )
    assert post_state.pending_deposits[2].pubkey == pubkey
    assert (
        post_state.pending_deposits[2].withdrawal_credentials
        == builder_deposit.withdrawal_credentials
    )


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
@always_bls
def test_fork_mixed_validity_validator_deposits_surrounding_builder_deposits(spec, phases, state):
    """
    Test fork with mixed-validity validator deposits surrounding builder deposits
    for the same unregistered pubkey:
    - Valid validator
    - Invalid validator
    - Valid builder
    - Invalid validator
    - Valid builder

    Any earlier valid validator deposit claims the pubkey for the rest of the
    queue. No builder is created and every deposit stays pending.
    """
    post_spec = phases[GLOAS]
    amount = post_spec.MIN_DEPOSIT_AMOUNT
    pubkey = builder_pubkeys[0]

    valid_validator_deposit = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=True
    )
    invalid_validator_deposit_1 = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=False
    )
    builder_deposit_1 = create_pending_deposit_for_builder(post_spec, pubkey, amount)
    invalid_validator_deposit_2 = create_pending_deposit_for_unregistered_validator(
        post_spec, pubkey, amount, signed=False
    )
    builder_deposit_2 = create_pending_deposit_for_builder(post_spec, pubkey, amount)

    state.pending_deposits = spec.PendingDeposits.of(
        valid_validator_deposit,
        invalid_validator_deposit_1,
        builder_deposit_1,
        invalid_validator_deposit_2,
        builder_deposit_2,
    )

    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.builders) == 0
    assert len(post_state.pending_deposits) == 5
    assert post_state.pending_deposits[0].pubkey == pubkey
    assert (
        post_state.pending_deposits[0].withdrawal_credentials
        == valid_validator_deposit.withdrawal_credentials
    )
    assert post_state.pending_deposits[1].signature == post_spec.bls.G2_POINT_AT_INFINITY
    assert (
        post_state.pending_deposits[2].withdrawal_credentials
        == builder_deposit_1.withdrawal_credentials
    )
    assert post_state.pending_deposits[3].signature == post_spec.bls.G2_POINT_AT_INFINITY
    assert (
        post_state.pending_deposits[4].withdrawal_credentials
        == builder_deposit_2.withdrawal_credentials
    )
