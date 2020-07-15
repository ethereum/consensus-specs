from typing import TypeVar

from remerkleable.basic import uint
from remerkleable.core import View
from remerkleable.byte_arrays import Bytes32


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
