from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8321_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.eip8321.randao import (
    activate_commitment,
    compute_hash_chain,
    get_commitment,
)
from eth_consensus_specs.test.helpers.state import next_slot


def run_process_randao(spec, state, block, valid=True):
    """
    Run ``process_randao``, yielding:
      - pre-state ('pre')
      - block ('block')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "block", block

    if not valid:
        expect_assertion_error(lambda: spec.process_randao(state, block.body))
        yield "post", None
        return

    spec.process_randao(state, block.body)

    yield "post", state


@with_eip8321_and_later
@spec_state_test
def test_hash_chain_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    commitment = activate_commitment(spec, state, proposer_index)

    epoch = spec.get_current_epoch(state)
    pre_mix = spec.get_randao_mix(state, epoch)

    block = build_empty_block(spec, state)
    reveal = block.body.hash_chain_reveal
    assert reveal != spec.Bytes32()
    assert spec.blake3(spec.HASH_CHAIN_RANDAO_DST + reveal) == commitment

    yield from run_process_randao(spec, state, block)

    # The raw reveal is folded in with a hash accumulator
    assert spec.get_randao_mix(state, epoch) == spec.blake3(pre_mix + reveal)
    # And the chain walks one link back
    assert state.randao_commitments[proposer_index] == reveal


@with_eip8321_and_later
@spec_state_test
def test_hash_chain_reveal_consumes_one_link_per_block(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    activate_commitment(spec, state, proposer_index)
    chain = compute_hash_chain(spec, proposer_index)

    # Two proposals by the same validator consume two distinct links
    for offset in range(2):
        block = build_empty_block(spec, state)
        assert block.body.hash_chain_reveal == chain[len(chain) - 2 - offset]
        spec.process_randao(state, block.body)
        assert state.randao_commitments[proposer_index] == chain[len(chain) - 2 - offset]


@with_eip8321_and_later
@spec_state_test
def test_unregistered_proposer_uses_bls_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    assert state.randao_commitments[proposer_index] == spec.Bytes32()

    epoch = spec.get_current_epoch(state)
    pre_mix = spec.get_randao_mix(state, epoch)

    block = build_empty_block(spec, state)
    assert block.body.hash_chain_reveal == spec.Bytes32()

    yield from run_process_randao(spec, state, block)

    assert spec.get_randao_mix(state, epoch) == spec.xor(
        pre_mix, spec.sha256(block.body.randao_reveal)
    )
    # An unregistered validator stays unregistered
    assert state.randao_commitments[proposer_index] == spec.Bytes32()


@with_eip8321_and_later
@spec_state_test
def test_invalid_hash_chain_reveal_not_preimage(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    activate_commitment(spec, state, proposer_index)

    block = build_empty_block(spec, state)
    # A link from another validator's chain is not a preimage of this commitment
    block.body.hash_chain_reveal = get_commitment(spec, proposer_index + 1)

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
def test_invalid_hash_chain_reveal_skips_a_link(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    activate_commitment(spec, state, proposer_index)
    chain = compute_hash_chain(spec, proposer_index)

    block = build_empty_block(spec, state)
    # Revealing two links back skips the commitment's direct preimage
    block.body.hash_chain_reveal = chain[len(chain) - 3]

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
def test_invalid_zero_hash_chain_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    block = build_empty_block(spec, state)

    # Committing to the hash of the zero word would let a zero reveal pass the chain
    # step, but the sentinel guard rejects it first
    state.randao_commitments[proposer_index] = spec.blake3(
        spec.HASH_CHAIN_RANDAO_DST + spec.Bytes32()
    )
    block.body.hash_chain_reveal = spec.Bytes32()

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_invalid_registered_proposer_with_bls_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)

    # Build the block while unregistered, so it carries a valid BLS reveal, then register
    block = build_empty_block(spec, state)
    activate_commitment(spec, state, proposer_index)

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
def test_invalid_registered_proposer_with_nonempty_bls_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    activate_commitment(spec, state, proposer_index)

    block = build_empty_block(spec, state)
    block.body.randao_reveal = spec.BLSSignature(b"\x11" * 96)

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_invalid_unregistered_proposer_with_hash_chain_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    assert state.randao_commitments[proposer_index] == spec.Bytes32()

    block = build_empty_block(spec, state)
    block.body.hash_chain_reveal = get_commitment(spec, proposer_index)

    yield from run_process_randao(spec, state, block, valid=False)


def build_block_with_hash_chain_reveal(spec, state, reveal):
    """
    Build a block for the current proposer carrying ``reveal`` on the hash-chain path.
    """
    block = build_empty_block(spec, state)
    block.body.randao_reveal = spec.G2_POINT_AT_INFINITY
    block.body.hash_chain_reveal = reveal
    return block


def next_slot_with_other_proposer(spec, state, proposer_index):
    """
    Advance within the epoch to the next slot with a different proposer.
    """
    epoch = spec.get_current_epoch(state)
    while True:
        next_slot(spec, state)
        assert spec.get_current_epoch(state) == epoch
        if spec.get_beacon_proposer_index(state) != proposer_index:
            return spec.get_beacon_proposer_index(state)


@with_eip8321_and_later
@spec_state_test
def test_hash_chain_reveal_only_updates_current_epoch_mix(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    activate_commitment(spec, state, proposer_index)

    epoch = spec.get_current_epoch(state)
    pre_mixes = [spec.Bytes32(mix) for mix in state.randao_mixes]

    block = build_empty_block(spec, state)
    yield from run_process_randao(spec, state, block)

    position = epoch % spec.EPOCHS_PER_HISTORICAL_VECTOR
    for index, mix in enumerate(state.randao_mixes):
        if index != position:
            assert mix == pre_mixes[index]
    assert state.randao_mixes[position] != pre_mixes[position]


@with_eip8321_and_later
@spec_state_test
def test_invalid_replay_of_previous_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    activate_commitment(spec, state, proposer_index)

    block = build_empty_block(spec, state)
    spec.process_randao(state, block.body)

    # The consumed reveal is now the commitment itself
    assert state.randao_commitments[proposer_index] == block.body.hash_chain_reveal

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
@always_bls
def test_invalid_exhausted_chain_cannot_fall_back_to_bls_reveal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    chain = compute_hash_chain(spec, proposer_index)

    # Valid legacy reveal, built while unregistered
    block = build_empty_block(spec, state)

    # Chain exhausted down to its secret
    state.randao_commitments[proposer_index] = chain[0]

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
def test_invalid_reveal_without_domain_separation_tag(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    reveal = spec.Bytes32(b"\x42" * 32)

    block = build_block_with_hash_chain_reveal(spec, state, reveal)
    # Commitment without the domain separation tag
    state.randao_commitments[proposer_index] = spec.blake3(reveal)

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
def test_invalid_reveal_committed_with_sha256(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    reveal = spec.Bytes32(b"\x42" * 32)

    block = build_block_with_hash_chain_reveal(spec, state, reveal)
    # Commitment under SHA 256 instead of BLAKE3
    state.randao_commitments[proposer_index] = spec.sha256(spec.HASH_CHAIN_RANDAO_DST + reveal)

    yield from run_process_randao(spec, state, block, valid=False)


@with_eip8321_and_later
@spec_state_test
def test_copied_commitment_cannot_cancel_victim_contribution(spec, state):
    """
    A copied commitment can only re-inject a public reveal, which must not cancel the mix.
    """
    next_slot(spec, state)
    victim_index = spec.get_beacon_proposer_index(state)
    commitment = activate_commitment(spec, state, victim_index)

    epoch = spec.get_current_epoch(state)
    pre_mix = spec.get_randao_mix(state, epoch)

    victim_block = build_empty_block(spec, state)
    reveal = victim_block.body.hash_chain_reveal
    spec.process_randao(state, victim_block.body)
    victim_mix = spec.get_randao_mix(state, epoch)

    copier_index = next_slot_with_other_proposer(spec, state, victim_index)
    copier_block = build_block_with_hash_chain_reveal(spec, state, reveal)
    state.randao_commitments[copier_index] = commitment

    yield from run_process_randao(spec, state, copier_block)

    post_mix = spec.get_randao_mix(state, epoch)
    assert post_mix == spec.blake3(victim_mix + reveal)
    assert post_mix != pre_mix
    assert post_mix != victim_mix
    assert state.randao_commitments[copier_index] == reveal


@with_eip8321_and_later
@spec_state_test
def test_mix_is_ordered_fold_of_mixed_reveals(spec, state):
    for index in range(0, len(state.validators), 2):
        activate_commitment(spec, state, index)

    next_slot(spec, state)
    epoch = spec.get_current_epoch(state)
    expected = spec.get_randao_mix(state, epoch)
    paths = set()

    while True:
        block = build_empty_block(spec, state)
        if block.body.hash_chain_reveal != spec.Bytes32():
            expected = spec.blake3(expected + block.body.hash_chain_reveal)
            paths.add("hash_chain")
        else:
            expected = spec.xor(expected, spec.sha256(block.body.randao_reveal))
            paths.add("bls")
        spec.process_randao(state, block.body)
        assert spec.get_randao_mix(state, epoch) == expected

        if (state.slot + 1) % spec.SLOTS_PER_EPOCH == 0:
            break
        next_slot(spec, state)

    assert paths == {"hash_chain", "bls"}
