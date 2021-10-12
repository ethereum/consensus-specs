import random
from eth2spec.test.context import (
    always_bls,
    fork_transition_test,
)
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing,
)
from eth2spec.test.helpers.proposer_slashings import (
    get_valid_proposer_slashing,
)
from eth2spec.test.helpers.fork_transition import (
    do_altair_fork,
    state_transition_across_slots,
    state_transition_across_slots_with_ignoring_proposers,
    transition_until_fork,
)
from eth2spec.test.helpers.inactivity_scores import (
    slash_some_validators_for_inactivity_scores_test,
)


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=1)
def test_transition_with_one_fourth_slashed_active_validators_pre_fork(
        state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    1/4 validators are slashed but still active at the fork transition.
    """
    # slash 1/4 validators
    slashed_indices = slash_some_validators_for_inactivity_scores_test(
        spec, state, rng=random.Random(5566), fraction=0.25)
    assert len(slashed_indices) > 0

    # check if some validators are slashed but still active
    for validator_index in slashed_indices:
        validator = state.validators[validator_index]
        assert validator.slashed
        assert spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert not spec.is_in_inactivity_leak(state)

    transition_until_fork(spec, state, fork_epoch)

    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # ensure that some of the current sync committee members are the slashed
    slashed_pubkeys = [state.validators[index].pubkey for index in slashed_indices]
    assert any(set(slashed_pubkeys).intersection(list(state.current_sync_committee.pubkeys)))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    # since the proposer might have been slashed, here we only create blocks with non-slashed proposers
    blocks.extend([
        post_tag(block) for block in
        state_transition_across_slots_with_ignoring_proposers(post_spec, state, to_slot, slashed_indices)
    ])

    # check post state
    for validator in state.validators:
        assert post_spec.is_active_validator(validator, post_spec.get_current_epoch(state))
    assert not post_spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@always_bls
def test_transition_with_attester_slashing_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create an attester slashing at the transition
    """
    transition_until_fork(spec, state, fork_epoch)

    yield "pre", state

    # NOTE: it can only be created with pre spec
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    operation_dict = {'attester_slashings': [attester_slashing]}

    # irregular state transition to handle fork:
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch, operation_dict=operation_dict)
    blocks = []
    blocks.append(post_tag(block))

    indices = set(attester_slashing.attestation_1.attesting_indices).intersection(
        attester_slashing.attestation_2.attesting_indices
    )
    assert len(indices) > 0
    for validator_index in indices:
        assert state.validators[validator_index].slashed

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        state_transition_across_slots(post_spec, state, to_slot)
    ])

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@always_bls
def test_transition_with_proposer_slashing_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create an attester slashing at the transition
    """
    transition_until_fork(spec, state, fork_epoch)

    yield "pre", state

    # NOTE: it can only be created with pre spec
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    operation_dict = {'proposer_slashings': [proposer_slashing]}

    # irregular state transition to handle fork:
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch, operation_dict=operation_dict)
    blocks = []
    blocks.append(post_tag(block))

    slashed_proposer = state.validators[proposer_slashing.signed_header_1.message.proposer_index]
    assert slashed_proposer.slashed

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        state_transition_across_slots(post_spec, state, to_slot)
    ])

    yield "blocks", blocks
    yield "post", state
