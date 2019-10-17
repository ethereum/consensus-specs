from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign, bls_aggregate_signatures
from eth2spec.utils.hash_function import hash
from eth2spec.utils.ssz.ssz_typing import Bitlist, BytesN, Bitvector
from eth2spec.utils.ssz.ssz_impl import chunkify, pack, hash_tree_root
from eth2spec.utils.merkle_minimal import get_merkle_tree, get_merkle_proof

BYTES_PER_CHUNK = 32


def get_valid_early_derived_secret_reveal(spec, state, epoch=None):
    current_epoch = spec.get_current_epoch(state)
    revealed_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    masker_index = spec.get_active_validator_indices(state, current_epoch)[0]

    if epoch is None:
        epoch = current_epoch + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING

    # Generate the secret that is being revealed
    reveal = bls_sign(
        message_hash=hash_tree_root(spec.Epoch(epoch)),
        privkey=privkeys[revealed_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    # Generate the mask (any random 32 bytes that don't reveal the masker's secret will do)
    mask = hash(reveal)
    # Generate masker's signature on the mask
    masker_signature = bls_sign(
        message_hash=mask,
        privkey=privkeys[masker_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    masked_reveal = bls_aggregate_signatures([reveal, masker_signature])

    return spec.EarlyDerivedSecretReveal(
        revealed_index=revealed_index,
        epoch=epoch,
        reveal=masked_reveal,
        masker_index=masker_index,
        mask=mask,
    )


def get_valid_custody_key_reveal(spec, state, period=None):
    current_epoch = spec.get_current_epoch(state)
    revealer_index = spec.get_active_validator_indices(state, current_epoch)[0]
    revealer = state.validators[revealer_index]

    if period is None:
        period = revealer.next_custody_secret_to_reveal

    epoch_to_sign = spec.get_randao_epoch_for_custody_period(period, revealer_index)

    # Generate the secret that is being revealed
    reveal = bls_sign(
        message_hash=hash_tree_root(spec.Epoch(epoch_to_sign)),
        privkey=privkeys[revealer_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch_to_sign,
        ),
    )
    return spec.CustodyKeyReveal(
        revealer_index=revealer_index,
        reveal=reveal,
    )


def bitlist_from_int(max_len, num_bits, n):
    return Bitlist[max_len](*[(n >> i) & 0b1 for i in range(num_bits)])


def get_valid_bit_challenge(spec, state, attestation, invalid_custody_bit=False):
    beacon_committee = spec.get_beacon_committee(
        state,
        attestation.data.slot,
        attestation.data.crosslink.shard,
    )
    responder_index = beacon_committee[0]
    challenger_index = beacon_committee[-1]

    epoch = spec.get_randao_epoch_for_custody_period(attestation.data.target.epoch,
                                                     responder_index)

    # Generate the responder key
    responder_key = bls_sign(
        message_hash=hash_tree_root(spec.Epoch(epoch)),
        privkey=privkeys[responder_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )

    chunk_count = spec.get_custody_chunk_count(attestation.data.crosslink)

    chunk_bits = bitlist_from_int(spec.MAX_CUSTODY_CHUNKS, chunk_count, 0)

    n = 0
    while spec.get_chunk_bits_root(chunk_bits) == attestation.custody_bits[0] ^ invalid_custody_bit:
        chunk_bits = bitlist_from_int(spec.MAX_CUSTODY_CHUNKS, chunk_count, n)
        n += 1

    return spec.CustodyBitChallenge(
        responder_index=responder_index,
        attestation=attestation,
        challenger_index=challenger_index,
        responder_key=responder_key,
        chunk_bits=chunk_bits,
    )


def custody_chunkify(spec, x):
    chunks = [bytes(x[i:i + spec.BYTES_PER_CUSTODY_CHUNK]) for i in range(0, len(x), spec.BYTES_PER_CUSTODY_CHUNK)]
    chunks[-1] = chunks[-1].ljust(spec.BYTES_PER_CUSTODY_CHUNK, b"\0")
    return chunks


def get_valid_custody_response(spec, state, bit_challenge, custody_data, challenge_index, invalid_chunk_bit=False):
    chunks = custody_chunkify(spec, custody_data)

    chunk_index = len(chunks) - 1
    chunk_bit = spec.get_custody_chunk_bit(bit_challenge.responder_key, chunks[chunk_index])

    while chunk_bit == bit_challenge.chunk_bits[chunk_index] ^ invalid_chunk_bit:
        chunk_index -= 1
        chunk_bit = spec.get_custody_chunk_bit(bit_challenge.responder_key, chunks[chunk_index])

    chunks_hash_tree_roots = [hash_tree_root(BytesN[spec.BYTES_PER_CUSTODY_CHUNK](chunk)) for chunk in chunks]
    chunks_hash_tree_roots += [
        hash_tree_root(BytesN[spec.BYTES_PER_CUSTODY_CHUNK](b"\0" * spec.BYTES_PER_CUSTODY_CHUNK))
        for i in range(2 ** spec.ceillog2(len(chunks)) - len(chunks))]
    data_tree = get_merkle_tree(chunks_hash_tree_roots)

    data_branch = get_merkle_proof(data_tree, chunk_index)

    bitlist_chunk_index = chunk_index // BYTES_PER_CHUNK
    bitlist_chunks = chunkify(pack(bit_challenge.chunk_bits))
    bitlist_tree = get_merkle_tree(bitlist_chunks, pad_to=spec.MAX_CUSTODY_CHUNKS // 256)
    bitlist_chunk_branch = get_merkle_proof(bitlist_tree, chunk_index // 256) + \
        [len(bit_challenge.chunk_bits).to_bytes(32, "little")]

    bitlist_chunk_index = chunk_index // 256

    chunk_bits_leaf = Bitvector[256](bit_challenge.chunk_bits[bitlist_chunk_index * 256:
                                     (bitlist_chunk_index + 1) * 256])

    return spec.CustodyResponse(
        challenge_index=challenge_index,
        chunk_index=chunk_index,
        chunk=BytesN[spec.BYTES_PER_CUSTODY_CHUNK](chunks[chunk_index]),
        data_branch=data_branch,
        chunk_bits_branch=bitlist_chunk_branch,
        chunk_bits_leaf=chunk_bits_leaf,
    )


def get_custody_test_vector(bytelength):
    ints = bytelength // 4
    return b"".join(i.to_bytes(4, "little") for i in range(ints))


def get_custody_merkle_root(data):
    return get_merkle_tree(chunkify(data))[-1][0]
