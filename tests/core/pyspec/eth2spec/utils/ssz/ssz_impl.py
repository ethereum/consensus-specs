from typing import TypeVar

from remerkleable.basic import uint
from remerkleable.core import View
from remerkleable.byte_arrays import Bytes32
from remerkleable.tree import gindex_bit_iter


def serialize(obj: View) -> bytes:
    return obj.encode_bytes()


def hash_tree_root(obj: View) -> Bytes32:
    return Bytes32(obj.get_backing().merkle_root())


def uint_to_bytes(n: uint) -> bytes:
    return serialize(n)


V = TypeVar('V', bound=View)


# Helper method for typing copies, and avoiding a example_input.copy() method call, instead of copy(example_input)
def copy(obj: V) -> V:
    return obj.copy()


def build_proof(anchor, leaf_index):
    if leaf_index <= 1:
        return []  # Nothing to prove / invalid index
    node = anchor
    proof = []
    # Walk down, top to bottom to the leaf
    bit_iter, _ = gindex_bit_iter(leaf_index)
    for bit in bit_iter:
        # Always take the opposite hand for the proof.
        # 1 = right as leaf, thus get left
        if bit:
            proof.append(node.get_left().merkle_root())
            node = node.get_right()
        else:
            proof.append(node.get_right().merkle_root())
            node = node.get_left()

    return list(reversed(proof))
