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
    assert spec.blake3_hash(spec.HASH_CHAIN_RANDAO_DST + reveal) == commitment

    yield from run_process_randao(spec, state, block)

    # The raw reveal is folded in with a hash accumulator
    assert spec.get_randao_mix(state, epoch) == spec.blake3_hash(pre_mix + reveal)
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
        pre_mix, spec.sha256_hash(block.body.randao_reveal)
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
    state.randao_commitments[proposer_index] = spec.blake3_hash(
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
