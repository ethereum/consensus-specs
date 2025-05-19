from typing import TypeVar

from remerkleable.basic import uint
from remerkleable.byte_arrays import Bytes32
from remerkleable.core import Type, View


def ssz_serialize(obj: View) -> bytes:
    return obj.encode_bytes()


def serialize(obj: View) -> bytes:
    return ssz_serialize(obj)


def ssz_deserialize(typ: Type[View], data: bytes) -> View:
    return typ.decode_bytes(data)


def deserialize(typ: Type[View], data: bytes) -> View:
    return ssz_deserialize(typ, data)


def hash_tree_root(obj: View) -> Bytes32:
    return Bytes32(obj.get_backing().merkle_root())


def uint_to_bytes(n: uint) -> bytes:
    return serialize(n)


V = TypeVar("V", bound=View)


# Helper method for typing copies, and avoiding a example_input.copy() method call, instead of copy(example_input)
def copy(obj: V) -> V:
    return obj.copy()
