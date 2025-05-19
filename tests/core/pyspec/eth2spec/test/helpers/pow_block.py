from random import Random

from eth2spec.utils.ssz.ssz_typing import uint256


class PowChain:
    blocks = []

    def __init__(self, blocks):
        self.blocks = blocks

    def __iter__(self):
        return iter(self.blocks)

    def head(self, offset=0):
        assert offset <= 0
        return self.blocks[offset - 1]

    def to_dict(self):
        return {block.block_hash: block for block in self.blocks}


def prepare_random_pow_block(spec, rng=Random(3131)):
    return spec.PowBlock(
        block_hash=spec.Hash32(spec.hash(bytearray(rng.getrandbits(8) for _ in range(32)))),
        parent_hash=spec.Hash32(spec.hash(bytearray(rng.getrandbits(8) for _ in range(32)))),
        total_difficulty=uint256(0),
    )


def prepare_random_pow_chain(spec, length, rng=Random(3131)) -> PowChain:
    assert length > 0
    chain = [prepare_random_pow_block(spec, rng)]
    for i in range(1, length):
        chain.append(prepare_random_pow_block(spec, rng))
        chain[i].parent_hash = chain[i - 1].block_hash
    return PowChain(chain)
