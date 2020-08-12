from typing import Dict, Sequence

from eth2spec.test.context import (
    PHASE0, MINIMAL,
    with_all_phases_except,
    spec_state_test,
    only_full_crosslink,
    with_configs,
)
from eth2spec.test.helpers.attestations import get_valid_on_time_attestation
from eth2spec.test.helpers.block import build_empty_block
from eth2spec.test.helpers.custody import (
    get_custody_slashable_test_vector,
    get_valid_chunk_challenge,
    get_valid_custody_chunk_response,
    get_valid_custody_key_reveal,
    get_valid_custody_slashing,
    get_valid_early_derived_secret_reveal,
)
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    get_committee_index_of_shard,
    get_sample_shard_block_body,
    get_shard_transitions,
)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to_valid_shard_slot, transition_to


def run_beacon_block(spec, state, block, valid=True):
    yield 'pre', state.copy()

    if not valid:
        signed_beacon_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)
        yield 'block', signed_beacon_block
        yield 'post', None
        return

    signed_beacon_block = state_transition_and_sign_block(spec, state, block)
    yield 'block', signed_beacon_block
    yield 'post', state


#
# Beacon block with non-empty shard transitions
#


def run_beacon_block_with_shard_blocks(spec, state, target_len_offset_slot, committee_index, shard, valid=True):
    transition_to(spec, state, state.slot + target_len_offset_slot)

    body = get_sample_shard_block_body(spec, is_max=True)
    shard_block = build_shard_block(spec, state, shard, body=body, slot=state.slot, signed=True)
    shard_block_dict: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {shard: [shard_block]}

    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)
    attestations = [
        get_valid_on_time_attestation(
            spec,
            state,
            index=committee_index,
            shard_transition=shard_transitions[shard],
            signed=True,
        )
        for shard in shard_block_dict.keys()
    ]

    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)
    beacon_block.body.attestations = attestations
    beacon_block.body.shard_transitions = shard_transitions

    pre_gasprice = state.shard_states[shard].gasprice
    pre_shard_states = state.shard_states.copy()
    yield 'pre', state.copy()

    if not valid:
        state_transition_and_sign_block(spec, state, beacon_block, expect_fail=True)
        yield 'block', beacon_block
        yield 'post', None
        return

    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)
    yield 'block', signed_beacon_block
    yield 'post', state

    for shard in range(spec.get_active_shard_count(state)):
        post_shard_state = state.shard_states[shard]
        if shard in shard_block_dict:
            # Shard state has been changed to state_transition result
            assert post_shard_state == shard_transitions[shard].shard_states[
                len(shard_transitions[shard].shard_states) - 1
            ]
            assert post_shard_state.slot == state.slot - 1
            if len((shard_block_dict[shard])) == 0:
                # `latest_block_root` is the same
                assert post_shard_state.latest_block_root == pre_shard_states[shard].latest_block_root
            if target_len_offset_slot == 1 and len(shard_block_dict[shard]) > 0:
                assert post_shard_state.gasprice > pre_gasprice


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_process_beacon_block_with_normal_shard_transition(spec, state):
    transition_to_valid_shard_slot(spec, state)

    target_len_offset_slot = 1
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot + target_len_offset_slot - 1)
    assert state.shard_states[shard].slot == state.slot - 1

    yield from run_beacon_block_with_shard_blocks(spec, state, target_len_offset_slot, committee_index, shard)


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_process_beacon_block_with_empty_proposal_transition(spec, state):
    transition_to_valid_shard_slot(spec, state)

    target_len_offset_slot = 1
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot + target_len_offset_slot - 1)
    assert state.shard_states[shard].slot == state.slot - 1

    yield from run_beacon_block_with_shard_blocks(spec, state, target_len_offset_slot, committee_index, shard)


#
# Beacon block with custody operations
#


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_with_shard_transition_with_custody_challenge_and_response(spec, state):
    transition_to_valid_shard_slot(spec, state)

    # build shard block
    shard = 0
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    body = get_sample_shard_block_body(spec)
    shard_block = build_shard_block(spec, state, shard, body=body, slot=state.slot, signed=True)
    shard_block_dict: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {shard: [shard_block]}
    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)
    attestation = get_valid_on_time_attestation(
        spec, state, index=committee_index,
        shard_transition=shard_transitions[shard], signed=True,
    )

    block = build_empty_block(spec, state, slot=state.slot + 1)
    block.body.attestations = [attestation]
    block.body.shard_transitions = shard_transitions

    # CustodyChunkChallenge operation
    challenge = get_valid_chunk_challenge(spec, state, attestation, shard_transitions[shard])
    block.body.chunk_challenges = [challenge]
    # CustodyChunkResponse operation
    chunk_challenge_index = state.custody_chunk_challenge_index
    custody_response = get_valid_custody_chunk_response(
        spec, state, challenge, chunk_challenge_index, block_length_or_custody_data=body)
    block.body.chunk_challenge_responses = [custody_response]

    yield from run_beacon_block(spec, state, block)


@with_all_phases_except([PHASE0])
@spec_state_test
@with_configs([MINIMAL])
def test_custody_key_reveal(spec, state):
    transition_to_valid_shard_slot(spec, state)
    transition_to(spec, state, state.slot + spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH)

    block = build_empty_block(spec, state, slot=state.slot + 1)
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)
    block.body.custody_key_reveals = [custody_key_reveal]

    yield from run_beacon_block(spec, state, block)


@with_all_phases_except([PHASE0])
@spec_state_test
def test_early_derived_secret_reveal(spec, state):
    transition_to_valid_shard_slot(spec, state)
    block = build_empty_block(spec, state, slot=state.slot + 1)
    early_derived_secret_reveal = get_valid_early_derived_secret_reveal(spec, state)
    block.body.early_derived_secret_reveals = [early_derived_secret_reveal]

    yield from run_beacon_block(spec, state, block)


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_custody_slashing(spec, state):
    transition_to_valid_shard_slot(spec, state)

    # Build shard block
    shard = 0
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    # Create slashable shard block body
    validator_index = spec.get_beacon_committee(state, state.slot, committee_index)[0]
    custody_secret = spec.get_custody_secret(
        state,
        validator_index,
        privkeys[validator_index],
        spec.get_current_epoch(state),
    )
    slashable_body = get_custody_slashable_test_vector(spec, custody_secret, length=100, slashable=True)
    shard_block = build_shard_block(spec, state, shard, body=slashable_body, slot=state.slot, signed=True)
    shard_block_dict: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {shard: [shard_block]}
    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)

    attestation = get_valid_on_time_attestation(
        spec, state, index=committee_index,
        shard_transition=shard_transitions[shard], signed=True,
    )
    block = build_empty_block(spec, state, slot=state.slot + 1)
    block.body.attestations = [attestation]
    block.body.shard_transitions = shard_transitions

    _, _, _ = run_beacon_block(spec, state, block)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    block = build_empty_block(spec, state, slot=state.slot + 1)
    custody_slashing = get_valid_custody_slashing(
        spec, state, attestation, shard_transitions[shard], custody_secret, slashable_body
    )
    block.body.custody_slashings = [custody_slashing]

    yield from run_beacon_block(spec, state, block)
