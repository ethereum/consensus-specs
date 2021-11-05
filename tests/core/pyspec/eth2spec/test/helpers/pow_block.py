from random import Random
from eth2spec.utils.ssz.ssz_typing import uint256


def prepare_empty_pow_block(spec, rng=Random(3131)):
    return spec.PowBlock(
        block_hash=spec.Hash32(spec.hash(bytearray(rng.getrandbits(8) for _ in range(32)))),
        parent_hash=spec.Hash32(spec.hash(bytearray(rng.getrandbits(8) for _ in range(32)))),
        total_difficulty=uint256(0),
        difficulty=uint256(0)
    )


def prepare_random_pow_chain(spec, length, rng=Random(3131)):
    assert length > 0
    chain = [prepare_empty_pow_block(spec, rng)]
    for i in range(1, length):
        chain.append(prepare_empty_pow_block(spec, rng))
        chain[i].parent_hash = chain[i - 1].block_hash
    return chain
