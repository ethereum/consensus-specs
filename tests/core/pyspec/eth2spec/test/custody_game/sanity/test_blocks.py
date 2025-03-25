from typing import Dict, Sequence

from eth2spec.test.context import (
    with_phases,
    spec_state_test,
    with_presets,
)
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.block import build_empty_block
from eth2spec.test.helpers.constants import (
    CUSTODY_GAME,
    MINIMAL,
)
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
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to_valid_shard_slot,
    transition_to,
)


def run_beacon_block(spec, state, block, valid=True):
    yield "pre", state.copy()

    if not valid:
        signed_beacon_block = state_transition_and_sign_block(
            spec, state, block, expect_fail=True
        )
        yield "block", signed_beacon_block
        yield "post", None
        return

    signed_beacon_block = state_transition_and_sign_block(spec, state, block)
    yield "block", signed_beacon_block
    yield "post", state


#
# Beacon block with custody operations
#


@with_phases([CUSTODY_GAME])
@spec_state_test
def test_with_shard_transition_with_custody_challenge_and_response(spec, state):
    transition_to_valid_shard_slot(spec, state)

    # build shard block
    shard = 0
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    body = get_sample_shard_block_body(spec)
    shard_block = build_shard_block(
        spec, state, shard, body=body, slot=state.slot, signed=True
    )
    shard_block_dict: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {
        shard: [shard_block]
    }
    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)
    attestation = get_valid_attestation(
        spec,
        state,
        index=committee_index,
        shard_transition=shard_transitions[shard],
        signed=True,
    )

    block = build_empty_block(spec, state, slot=state.slot + 1)
    block.body.attestations = [attestation]
    block.body.shard_transitions = shard_transitions

    # CustodyChunkChallenge operation
    challenge = get_valid_chunk_challenge(
        spec, state, attestation, shard_transitions[shard]
    )
    block.body.chunk_challenges = [challenge]
    # CustodyChunkResponse operation
    chunk_challenge_index = state.custody_chunk_challenge_index
    custody_response = get_valid_custody_chunk_response(
        spec, state, challenge, chunk_challenge_index, block_length_or_custody_data=body
    )
    block.body.chunk_challenge_responses = [custody_response]

    yield from run_beacon_block(spec, state, block)


@with_phases([CUSTODY_GAME])
@spec_state_test
@with_presets([MINIMAL])
def test_custody_key_reveal(spec, state):
    transition_to_valid_shard_slot(spec, state)
    transition_to(
        spec, state, state.slot + spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH
    )

    block = build_empty_block(spec, state, slot=state.slot + 1)
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)
    block.body.custody_key_reveals = [custody_key_reveal]

    yield from run_beacon_block(spec, state, block)


@with_phases([CUSTODY_GAME])
@spec_state_test
def test_early_derived_secret_reveal(spec, state):
    transition_to_valid_shard_slot(spec, state)
    block = build_empty_block(spec, state, slot=state.slot + 1)
    early_derived_secret_reveal = get_valid_early_derived_secret_reveal(spec, state)
    block.body.early_derived_secret_reveals = [early_derived_secret_reveal]

    yield from run_beacon_block(spec, state, block)


@with_phases([CUSTODY_GAME])
@spec_state_test
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
    slashable_body = get_custody_slashable_test_vector(
        spec, custody_secret, length=100, slashable=True
    )
    shard_block = build_shard_block(
        spec, state, shard, body=slashable_body, slot=state.slot, signed=True
    )
    shard_block_dict: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {
        shard: [shard_block]
    }
    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)

    attestation = get_valid_attestation(
        spec,
        state,
        index=committee_index,
        shard_transition=shard_transitions[shard],
        signed=True,
    )
    block = build_empty_block(spec, state, slot=state.slot + 1)
    block.body.attestations = [attestation]
    block.body.shard_transitions = shard_transitions

    _, _, _ = run_beacon_block(spec, state, block)

    transition_to(
        spec,
        state,
        state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1),
    )

    block = build_empty_block(spec, state, slot=state.slot + 1)
    custody_slashing = get_valid_custody_slashing(
        spec,
        state,
        attestation,
        shard_transitions[shard],
        custody_secret,
        slashable_body,
    )
    block.body.custody_slashings = [custody_slashing]

    yield from run_beacon_block(spec, state, block)
