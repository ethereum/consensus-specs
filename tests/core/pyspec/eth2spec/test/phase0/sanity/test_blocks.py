from random import Random
from eth2spec.utils import bls

from eth2spec.test.helpers.state import (
    get_balance, state_transition_and_sign_block,
    next_slot, next_epoch, next_epoch_via_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot, build_empty_block,
    sign_block,
    transition_unsigned_block,
)
from eth2spec.test.helpers.keys import pubkeys
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
    get_valid_attester_slashing,
    get_indexed_attestation_participants,
    get_max_attester_slashings,
)
from eth2spec.test.helpers.proposer_slashings import get_valid_proposer_slashing, check_proposer_slashing_effect
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.deposits import prepare_state_and_deposit
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_empty_signed_execution_payload_header,
    compute_el_block_hash,
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits
from eth2spec.test.helpers.multi_operations import (
    run_slash_and_exit,
    run_test_full_random_operations,
)
from eth2spec.test.helpers.sync_committee import (
    compute_committee_indices,
    compute_sync_committee_participant_reward_and_penalty,
)
from eth2spec.test.helpers.constants import PHASE0, MINIMAL
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_electra,
    is_post_capella,
    is_post_eip7732,
)
from eth2spec.test.context import (
    spec_test, spec_state_test, dump_skipping_message,
    with_phases, with_all_phases, single_phase,
    expect_assertion_error, always_bls,
    with_presets,
    with_custom_state,
    large_validator_set,
)


@with_all_phases
@spec_state_test
def test_invalid_prev_slot_block_transition(spec, state):
    # Go to clean slot
    spec.process_slots(state, state.slot + 1)
    # Make a block for it
    block = build_empty_block(spec, state, slot=state.slot)
    proposer_index = spec.get_beacon_proposer_index(state)
    # Transition to next slot, above block will not be invalid on top of new state.
    spec.process_slots(state, state.slot + 1)

    yield 'pre', state
    # State is beyond block slot, but the block can still be realistic when invalid.
    # Try the transition, and update the state root to where it is halted. Then sign with the supposed proposer.
    expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
    block.state_root = state.hash_tree_root()
    signed_block = sign_block(spec, state, block, proposer_index=proposer_index)
    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_invalid_same_slot_block_transition(spec, state):
    # Same slot on top of pre-state, but move out of slot 0 first.
    spec.process_slots(state, state.slot + 1)

    block = build_empty_block(spec, state, slot=state.slot)

    yield 'pre', state

    assert state.slot == block.slot

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_empty_block_transition(spec, state):
    pre_slot = state.slot
    pre_eth1_votes = len(state.eth1_data_votes)
    pre_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.eth1_data_votes) == pre_eth1_votes + 1
    assert spec.get_block_root_at_slot(state, pre_slot) == signed_block.message.parent_root
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != pre_mix


@with_all_phases
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=large_validator_set, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_empty_block_transition_large_validator_set(spec, state):
    pre_slot = state.slot
    pre_eth1_votes = len(state.eth1_data_votes)
    pre_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.eth1_data_votes) == pre_eth1_votes + 1
    assert spec.get_block_root_at_slot(state, pre_slot) == signed_block.message.parent_root
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != pre_mix


def process_and_sign_block_without_header_validations(spec, state, block):
    """
    Artificially bypass the restrictions in the state transition to transition and sign block

    WARNING UNSAFE: Only use when generating valid-looking invalid blocks for test vectors
    """

    # Perform single mutation in `process_block_header`
    state.latest_block_header = spec.BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=spec.Bytes32(),
        body_root=block.body.hash_tree_root(),
    )
    if is_post_bellatrix(spec) and not is_post_eip7732(spec):
        if spec.is_execution_enabled(state, block.body):
            spec.process_execution_payload(state, block.body, spec.EXECUTION_ENGINE)

    # Perform rest of process_block transitions
    spec.process_randao(state, block.body)
    spec.process_eth1_data(state, block.body)
    spec.process_operations(state, block.body)
    if is_post_altair(spec):
        spec.process_sync_aggregate(state, block.body.sync_aggregate)

    # Insert post-state root
    block.state_root = state.hash_tree_root()

    # Sign block
    return sign_block(spec, state, block)


@with_phases([PHASE0])
@spec_state_test
def test_invalid_proposal_for_genesis_slot(spec, state):
    assert state.slot == spec.GENESIS_SLOT

    yield 'pre', state

    block = build_empty_block(spec, state, spec.GENESIS_SLOT)
    block.parent_root = state.latest_block_header.hash_tree_root()

    # Show that normal path through transition fails
    failed_state = state.copy()
    expect_assertion_error(
        lambda: spec.state_transition(failed_state, spec.SignedBeaconBlock(message=block), validate_result=False)
    )

    # Artificially bypass the restriction in the state transition to transition and sign block for test vectors
    signed_block = process_and_sign_block_without_header_validations(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_invalid_parent_from_same_slot(spec, state):
    yield 'pre', state

    parent_block = build_empty_block_for_next_slot(spec, state)
    signed_parent_block = state_transition_and_sign_block(spec, state, parent_block)

    child_block = parent_block.copy()
    child_block.parent_root = state.latest_block_header.hash_tree_root()

    if is_post_eip7732(spec):
        child_block.body.signed_execution_payload_header = build_empty_signed_execution_payload_header(spec, state)
    elif is_post_bellatrix(spec):
        child_block.body.execution_payload = build_empty_execution_payload(spec, state)

    child_block.parent_root = state.latest_block_header.hash_tree_root()
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        child_block.body.signed_execution_payload_header.message.block_hash = compute_el_block_hash(
            spec, payload, state)
    elif is_post_bellatrix(spec):
        child_block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, child_block)

    # Show that normal path through transition fails
    failed_state = state.copy()
    expect_assertion_error(
        lambda: spec.state_transition(failed_state, spec.SignedBeaconBlock(message=child_block), validate_result=False)
    )

    # Artificially bypass the restriction in the state transition to transition and sign block for test vectors
    signed_child_block = process_and_sign_block_without_header_validations(spec, state, child_block)

    yield 'blocks', [signed_parent_block, signed_child_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_invalid_incorrect_state_root(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.state_root = b"\xaa" * 32
    signed_block = sign_block(spec, state, block)

    expect_assertion_error(lambda: spec.state_transition(state, signed_block))

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_all_zeroed_sig(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    invalid_signed_block = spec.SignedBeaconBlock(message=block)
    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_block_sig(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_PROPOSER, spec.compute_epoch_at_slot(block.slot))
    signing_root = spec.compute_signing_root(block, domain)
    invalid_signed_block = spec.SignedBeaconBlock(
        message=block,
        signature=bls.Sign(123456, signing_root)
    )
    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_proposer_index_sig_from_expected_proposer(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    expect_proposer_index = block.proposer_index

    # Set invalid proposer index but correct signature wrt expected proposer
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    active_indices = [i for i in active_indices if i != block.proposer_index]
    block.proposer_index = active_indices[0]  # invalid proposer index

    invalid_signed_block = sign_block(spec, state, block, expect_proposer_index)

    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_proposer_index_sig_from_proposer_index(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    # Set invalid proposer index but correct signature wrt proposer_index
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    active_indices = [i for i in active_indices if i != block.proposer_index]
    block.proposer_index = active_indices[0]  # invalid proposer index

    invalid_signed_block = sign_block(spec, state, block, block.proposer_index)

    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_skipped_slots(spec, state):
    pre_slot = state.slot
    yield 'pre', state

    block = build_empty_block(spec, state, state.slot + 4)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != spec.Bytes32()
    for slot in range(pre_slot, state.slot):
        assert spec.get_block_root_at_slot(state, slot) == block.parent_root


@with_all_phases
@spec_state_test
def test_empty_epoch_transition(spec, state):
    pre_slot = state.slot
    yield 'pre', state

    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    for slot in range(pre_slot, state.slot):
        assert spec.get_block_root_at_slot(state, slot) == block.parent_root


@with_all_phases
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=large_validator_set, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_empty_epoch_transition_large_validator_set(spec, state):
    pre_slot = state.slot
    yield 'pre', state

    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    for slot in range(pre_slot, state.slot):
        assert spec.get_block_root_at_slot(state, slot) == block.parent_root


@with_all_phases
@spec_state_test
def test_empty_epoch_transition_not_finalizing(spec, state):
    if spec.SLOTS_PER_EPOCH > 8:
        return dump_skipping_message("Skip mainnet config for saving time."
                                     " Minimal config suffice to cover the target-of-test.")

    # copy for later balance lookups.
    pre_balances = list(state.balances)
    yield 'pre', state

    spec.process_slots(state, state.slot + (spec.SLOTS_PER_EPOCH * 5))
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    assert state.finalized_checkpoint.epoch < spec.get_current_epoch(state) - 4
    for index in range(len(state.validators)):
        assert state.balances[index] < pre_balances[index]


@with_all_phases
@spec_state_test
def test_proposer_self_slashing(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    assert not state.validators[block.proposer_index].slashed

    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=block.proposer_index, signed_1=True, signed_2=True)
    block.body.proposer_slashings.append(proposer_slashing)

    # The header is processed *before* the block body:
    # the proposer was not slashed before the body, thus the block is valid.
    signed_block = state_transition_and_sign_block(spec, state, block)
    # The proposer slashed themselves.
    assert state.validators[block.proposer_index].slashed

    yield 'blocks', [signed_block]
    yield 'post', state


@with_all_phases
@spec_state_test
def test_proposer_slashing(spec, state):
    # copy for later balance lookups.
    pre_state = state.copy()
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_index = proposer_slashing.signed_header_1.message.proposer_index

    assert not state.validators[slashed_index].slashed

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings.append(proposer_slashing)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    check_proposer_slashing_effect(spec, pre_state, state, slashed_index, block)


@with_all_phases
@spec_state_test
def test_invalid_duplicate_proposer_slashings_same_block(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_index = proposer_slashing.signed_header_1.message.proposer_index
    assert not state.validators[slashed_index].slashed

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = [proposer_slashing, proposer_slashing]
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_invalid_similar_proposer_slashings_same_block(spec, state):
    slashed_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]

    # Same validator, but different slashable offences in the same block
    proposer_slashing_1 = get_valid_proposer_slashing(spec, state, random_root=b'\xaa' * 32,
                                                      slashed_index=slashed_index,
                                                      signed_1=True, signed_2=True)
    proposer_slashing_2 = get_valid_proposer_slashing(spec, state, random_root=b'\xbb' * 32,
                                                      slashed_index=slashed_index,
                                                      signed_1=True, signed_2=True)
    assert not state.validators[slashed_index].slashed

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = [proposer_slashing_1, proposer_slashing_2]
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_multiple_different_proposer_slashings_same_block(spec, state):
    pre_state = state.copy()

    num_slashings = 3
    proposer_slashings = []
    for i in range(num_slashings):
        slashed_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[i]
        assert not state.validators[slashed_index].slashed

        proposer_slashing = get_valid_proposer_slashing(spec, state,
                                                        slashed_index=slashed_index,
                                                        signed_1=True, signed_2=True)
        proposer_slashings.append(proposer_slashing)

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = proposer_slashings

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    for proposer_slashing in proposer_slashings:
        slashed_index = proposer_slashing.signed_header_1.message.proposer_index
        check_proposer_slashing_effect(spec, pre_state, state, slashed_index, block)


def check_attester_slashing_effect(spec, pre_state, state, slashed_indices):
    for slashed_index in slashed_indices:
        slashed_validator = state.validators[slashed_index]
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
        # lost whistleblower reward
        assert get_balance(state, slashed_index) < get_balance(pre_state, slashed_index)

    proposer_index = spec.get_beacon_proposer_index(state)
    # gained whistleblower reward
    assert get_balance(state, proposer_index) > get_balance(pre_state, proposer_index)


@with_all_phases
@spec_state_test
def test_attester_slashing(spec, state):
    # copy for later balance lookups.
    pre_state = state.copy()

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)

    assert not any(state.validators[i].slashed for i in slashed_indices)

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings.append(attester_slashing)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    check_attester_slashing_effect(spec, pre_state, state, slashed_indices)


@with_all_phases
@spec_state_test
def test_invalid_duplicate_attester_slashing_same_block(spec, state):
    if get_max_attester_slashings(spec) < 2:
        return dump_skipping_message("Skip test if config cannot handle multiple AttesterSlashings per block")

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    attester_slashings = [attester_slashing, attester_slashing.copy()]
    slashed_indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)

    assert not any(state.validators[i].slashed for i in slashed_indices)

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings = attester_slashings

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


# TODO All AttesterSlashing tests should be adopted for SHARDING and later but helper support is not yet there

@with_all_phases
@spec_state_test
def test_multiple_attester_slashings_no_overlap(spec, state):
    if get_max_attester_slashings(spec) < 2:
        return dump_skipping_message("Skip test if config cannot handle multiple AttesterSlashings per block")

    # copy for later balance lookups.
    pre_state = state.copy()

    full_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[:8]
    half_length = len(full_indices) // 2

    attester_slashing_1 = get_valid_attester_slashing_by_indices(
        spec, state,
        full_indices[:half_length], signed_1=True, signed_2=True,
    )
    attester_slashing_2 = get_valid_attester_slashing_by_indices(
        spec, state,
        full_indices[half_length:], signed_1=True, signed_2=True,
    )
    attester_slashings = [attester_slashing_1, attester_slashing_2]

    assert not any(state.validators[i].slashed for i in full_indices)

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings = attester_slashings

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    check_attester_slashing_effect(spec, pre_state, state, full_indices)


@with_all_phases
@spec_state_test
def test_multiple_attester_slashings_partial_overlap(spec, state):
    if get_max_attester_slashings(spec) < 2:
        return dump_skipping_message("Skip test if config cannot handle multiple AttesterSlashings per block")

    # copy for later balance lookups.
    pre_state = state.copy()

    full_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[:8]
    one_third_length = len(full_indices) // 3

    attester_slashing_1 = get_valid_attester_slashing_by_indices(
        spec, state,
        full_indices[:one_third_length * 2], signed_1=True, signed_2=True,
    )
    attester_slashing_2 = get_valid_attester_slashing_by_indices(
        spec, state,
        full_indices[one_third_length:], signed_1=True, signed_2=True,
    )
    attester_slashings = [attester_slashing_1, attester_slashing_2]

    assert not any(state.validators[i].slashed for i in full_indices)

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings = attester_slashings

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    check_attester_slashing_effect(spec, pre_state, state, full_indices)


@with_all_phases
@spec_state_test
def test_proposer_after_inactive_index(spec, state):
    # disable some low validator index to check after for
    inactive_index = 10
    state.validators[inactive_index].exit_epoch = spec.get_current_epoch(state)

    # skip forward, get brand new proposers
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)
    while True:
        proposer_index = spec.get_beacon_proposer_index(state)
        if proposer_index > inactive_index:
            # found a proposer that has a higher index than a disabled validator
            yield 'pre', state
            # test if the proposer can be recognized correctly after the inactive validator
            signed_block = state_transition_and_sign_block(spec, state, build_empty_block_for_next_slot(spec, state))
            yield 'blocks', [signed_block]
            yield 'post', state
            break
        next_slot(spec, state)


@with_all_phases
@spec_state_test
def test_high_proposer_index(spec, state):
    # disable a good amount of validators to make the active count lower, for a faster test
    current_epoch = spec.get_current_epoch(state)
    for i in range(len(state.validators) // 3):
        state.validators[i].exit_epoch = current_epoch

    # skip forward, get brand new proposers
    state.slot = spec.SLOTS_PER_EPOCH * 2
    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    active_count = len(spec.get_active_validator_indices(state, current_epoch))
    while True:
        proposer_index = spec.get_beacon_proposer_index(state)
        if proposer_index >= active_count:
            # found a proposer that has a higher index than the active validator count
            yield 'pre', state
            # test if the proposer can be recognized correctly, even while it has a high index.
            signed_block = state_transition_and_sign_block(spec, state, build_empty_block_for_next_slot(spec, state))
            yield 'blocks', [signed_block]
            yield 'post', state
            break
        next_slot(spec, state)


@with_all_phases
@spec_state_test
def test_invalid_only_increase_deposit_count(spec, state):
    # Make the state expect a deposit, then don't provide it.
    state.eth1_data.deposit_count += 1
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_deposit_in_block(spec, state):
    initial_registry_len = len(state.validators)
    initial_balances_len = len(state.balances)

    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    if is_post_electra(spec):
        balance = state.pending_deposits[0].amount
    else:
        balance = get_balance(state, validator_index)

    assert len(state.validators) == initial_registry_len + 1
    assert len(state.balances) == initial_balances_len + 1
    assert balance == spec.MAX_EFFECTIVE_BALANCE
    assert state.validators[validator_index].pubkey == pubkeys[validator_index]


@with_all_phases
@spec_state_test
def test_invalid_duplicate_deposit_same_block(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    # The same deposit of the same validator
    for _ in range(2):
        block.body.deposits.append(deposit)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_deposit_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)

    initial_registry_len = len(state.validators)
    initial_balances_len = len(state.balances)
    validator_pre_balance = get_balance(state, validator_index)

    pre_state = state.copy()
    yield 'pre', pre_state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.validators) == initial_registry_len
    assert len(state.balances) == initial_balances_len

    # Altair introduces sync committee (sm) reward and penalty
    sync_committee_reward = sync_committee_penalty = 0
    if is_post_altair(spec):
        committee_indices = compute_committee_indices(state, state.current_sync_committee)
        committee_bits = block.body.sync_aggregate.sync_committee_bits
        sync_committee_reward, sync_committee_penalty = compute_sync_committee_participant_reward_and_penalty(
            spec,
            pre_state,
            validator_index,
            committee_indices,
            committee_bits,
        )

    balance = get_balance(state, validator_index)
    if is_post_electra(spec):
        balance += state.pending_deposits[0].amount

    assert balance == (
        validator_pre_balance + amount + sync_committee_reward - sync_committee_penalty
    )


@with_all_phases
@spec_state_test
def test_attestation(spec, state):
    next_epoch(spec, state)

    yield 'pre', state

    attestation_block = build_empty_block(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    index = 0
    # if spec.fork == SHARDING:
    #     TODO add shard data to block to vote on

    attestation = get_valid_attestation(spec, state, index=index, signed=True)

    if not is_post_altair(spec):
        pre_current_attestations_len = len(state.current_epoch_attestations)

    # Add to state via block transition
    attestation_block.body.attestations.append(attestation)
    signed_attestation_block = state_transition_and_sign_block(spec, state, attestation_block)

    if not is_post_altair(spec):
        assert len(state.current_epoch_attestations) == pre_current_attestations_len + 1
        # Epoch transition should move to previous_epoch_attestations
        pre_current_attestations_root = spec.hash_tree_root(state.current_epoch_attestations)
    else:
        pre_current_epoch_participation_root = spec.hash_tree_root(state.current_epoch_participation)

    epoch_block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_epoch_block = state_transition_and_sign_block(spec, state, epoch_block)

    yield 'blocks', [signed_attestation_block, signed_epoch_block]
    yield 'post', state

    if not is_post_altair(spec):
        assert len(state.current_epoch_attestations) == 0
        assert spec.hash_tree_root(state.previous_epoch_attestations) == pre_current_attestations_root
    else:
        for index in range(len(state.validators)):
            assert state.current_epoch_participation[index] == spec.ParticipationFlags(0b0000_0000)
        assert spec.hash_tree_root(state.previous_epoch_participation) == pre_current_epoch_participation_root


@with_all_phases
@spec_state_test
def test_duplicate_attestation_same_block(spec, state):
    next_epoch(spec, state)

    yield 'pre', state

    attestation_block = build_empty_block(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    index = 0

    attestation = get_valid_attestation(spec, state, index=index, signed=True)

    if not is_post_altair(spec):
        pre_current_attestations_len = len(state.current_epoch_attestations)

    # Add to state via block transition
    for _ in range(2):
        attestation_block.body.attestations.append(attestation)
    signed_attestation_block = state_transition_and_sign_block(spec, state, attestation_block)

    if not is_post_altair(spec):
        assert len(state.current_epoch_attestations) == pre_current_attestations_len + 2
        # Epoch transition should move to previous_epoch_attestations
        pre_current_attestations_root = spec.hash_tree_root(state.current_epoch_attestations)
    else:
        pre_current_epoch_participation_root = spec.hash_tree_root(state.current_epoch_participation)

    epoch_block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_epoch_block = state_transition_and_sign_block(spec, state, epoch_block)

    yield 'blocks', [signed_attestation_block, signed_epoch_block]
    yield 'post', state

    if not is_post_altair(spec):
        assert len(state.current_epoch_attestations) == 0
        assert spec.hash_tree_root(state.previous_epoch_attestations) == pre_current_attestations_root
    else:
        for index in range(len(state.validators)):
            assert state.current_epoch_participation[index] == spec.ParticipationFlags(0b0000_0000)
        assert spec.hash_tree_root(state.previous_epoch_participation) == pre_current_epoch_participation_root


# After SHARDING is enabled, a committee is computed for SHARD_COMMITTEE_PERIOD slots ago,
# exceeding the minimal-config randao mixes memory size.
# Applies to all voluntary-exit sanity block tests.
# TODO: when integrating SHARDING tests, voluntary-exit tests may need to change.

@with_all_phases
@spec_state_test
def test_voluntary_exit(spec, state):
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]

    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    signed_exits = prepare_signed_exits(spec, state, [validator_index])
    yield 'pre', state

    # Add to state via block transition
    initiate_exit_block = build_empty_block_for_next_slot(spec, state)
    initiate_exit_block.body.voluntary_exits = signed_exits
    signed_initiate_exit_block = state_transition_and_sign_block(spec, state, initiate_exit_block)

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    # Process within epoch transition
    exit_block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_exit_block = state_transition_and_sign_block(spec, state, exit_block)

    yield 'blocks', [signed_initiate_exit_block, signed_exit_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_invalid_duplicate_validator_exit_same_block(spec, state):
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]

    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Same index tries to exit twice, but should only be able to do so once.
    signed_exits = prepare_signed_exits(spec, state, [validator_index, validator_index])
    yield 'pre', state

    # Add to state via block transition
    initiate_exit_block = build_empty_block_for_next_slot(spec, state)
    initiate_exit_block.body.voluntary_exits = signed_exits
    signed_initiate_exit_block = state_transition_and_sign_block(spec, state, initiate_exit_block, expect_fail=True)

    yield 'blocks', [signed_initiate_exit_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_multiple_different_validator_exits_same_block(spec, state):
    validator_indices = [
        spec.get_active_validator_indices(state, spec.get_current_epoch(state))[i]
        for i in range(3)
    ]
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    signed_exits = prepare_signed_exits(spec, state, validator_indices)
    yield 'pre', state

    # Add to state via block transition
    initiate_exit_block = build_empty_block_for_next_slot(spec, state)
    initiate_exit_block.body.voluntary_exits = signed_exits
    signed_initiate_exit_block = state_transition_and_sign_block(spec, state, initiate_exit_block)

    for index in validator_indices:
        assert state.validators[index].exit_epoch < spec.FAR_FUTURE_EPOCH

    # Process within epoch transition
    exit_block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_exit_block = state_transition_and_sign_block(spec, state, exit_block)

    yield 'blocks', [signed_initiate_exit_block, signed_exit_block]
    yield 'post', state

    for index in validator_indices:
        assert state.validators[index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_slash_and_exit_same_index(spec, state):
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    yield from run_slash_and_exit(spec, state, validator_index, validator_index, valid=False)


@with_all_phases
@spec_state_test
def test_slash_and_exit_diff_index(spec, state):
    slash_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    exit_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-2]
    yield from run_slash_and_exit(spec, state, slash_index, exit_index)


@with_all_phases
@spec_state_test
def test_balance_driven_status_transitions(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[-1]

    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # set validator balance to below ejection threshold
    state.validators[validator_index].effective_balance = spec.config.EJECTION_BALANCE

    yield 'pre', state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


# Requires always_bls because historical root period and sync committee period is same length
# so this epoch transition also computes new sync committees which requires aggregation
@with_all_phases
@spec_state_test
@always_bls
def test_historical_batch(spec, state):
    state.slot += spec.SLOTS_PER_HISTORICAL_ROOT - (state.slot % spec.SLOTS_PER_HISTORICAL_ROOT) - 1
    pre_historical_roots = state.historical_roots.copy()

    if is_post_capella(spec):
        pre_historical_summaries = state.historical_summaries.copy()

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    assert spec.get_current_epoch(state) % (spec.SLOTS_PER_HISTORICAL_ROOT // spec.SLOTS_PER_EPOCH) == 0

    # check history update
    if is_post_capella(spec):
        # Frozen `historical_roots`
        assert state.historical_roots == pre_historical_roots
        assert len(state.historical_summaries) == len(pre_historical_summaries) + 1
    else:
        assert len(state.historical_roots) == len(pre_historical_roots) + 1


@with_all_phases
@with_presets([MINIMAL], reason="suffices to test eth1 data voting without long voting period")
@spec_state_test
def test_eth1_data_votes_consensus(spec, state):
    voting_period_slots = spec.EPOCHS_PER_ETH1_VOTING_PERIOD * spec.SLOTS_PER_EPOCH

    offset_block = build_empty_block(spec, state, slot=voting_period_slots - 1)
    state_transition_and_sign_block(spec, state, offset_block)
    yield 'pre', state

    a = b'\xaa' * 32
    b = b'\xbb' * 32
    c = b'\xcc' * 32

    blocks = []

    for i in range(0, voting_period_slots):
        block = build_empty_block_for_next_slot(spec, state)
        # wait for over 50% for A, then start voting B
        block.body.eth1_data.block_hash = b if i * 2 > voting_period_slots else a
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    assert len(state.eth1_data_votes) == voting_period_slots
    assert state.eth1_data.block_hash == a

    # transition to next eth1 voting period
    block = build_empty_block_for_next_slot(spec, state)
    block.body.eth1_data.block_hash = c
    signed_block = state_transition_and_sign_block(spec, state, block)
    blocks.append(signed_block)

    yield 'blocks', blocks
    yield 'post', state

    assert state.eth1_data.block_hash == a
    assert state.slot % voting_period_slots == 0
    assert len(state.eth1_data_votes) == 1
    assert state.eth1_data_votes[0].block_hash == c


@with_all_phases
@with_presets([MINIMAL], reason="suffices to test eth1 data voting without long voting period")
@spec_state_test
def test_eth1_data_votes_no_consensus(spec, state):
    voting_period_slots = spec.EPOCHS_PER_ETH1_VOTING_PERIOD * spec.SLOTS_PER_EPOCH

    pre_eth1_hash = state.eth1_data.block_hash

    offset_block = build_empty_block(spec, state, slot=voting_period_slots - 1)
    state_transition_and_sign_block(spec, state, offset_block)
    yield 'pre', state

    a = b'\xaa' * 32
    b = b'\xbb' * 32

    blocks = []

    for i in range(0, voting_period_slots):
        block = build_empty_block_for_next_slot(spec, state)
        # wait for precisely 50% for A, then start voting B for other 50%
        block.body.eth1_data.block_hash = b if i * 2 >= voting_period_slots else a
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    assert len(state.eth1_data_votes) == voting_period_slots
    assert state.eth1_data.block_hash == pre_eth1_hash

    yield 'blocks', blocks
    yield 'post', state


@with_all_phases
@spec_state_test
def test_full_random_operations_0(spec, state):
    yield from run_test_full_random_operations(spec, state, rng=Random(2020))


@with_all_phases
@spec_state_test
def test_full_random_operations_1(spec, state):
    yield from run_test_full_random_operations(spec, state, rng=Random(2021))


@with_all_phases
@spec_state_test
def test_full_random_operations_2(spec, state):
    yield from run_test_full_random_operations(spec, state, rng=Random(2022))


@with_all_phases
@spec_state_test
def test_full_random_operations_3(spec, state):
    yield from run_test_full_random_operations(spec, state, rng=Random(2023))
