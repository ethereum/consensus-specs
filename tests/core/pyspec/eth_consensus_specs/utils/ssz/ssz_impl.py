from ssz.ssz_base import SSZType
from ssz.uint import BaseUint as Uint

from eth_consensus_specs.utils.ssz.bytes import Bytes32


def ssz_serialize(obj: SSZType) -> bytes:
    return obj.encode_bytes()


def serialize(obj: SSZType) -> bytes:
    return ssz_serialize(obj)


def ssz_deserialize(typ: type[SSZType], data: bytes) -> SSZType:
    return typ.decode_bytes(data)


def deserialize(typ: type[SSZType], data: bytes) -> SSZType:
    return ssz_deserialize(typ, data)


def hash_tree_root(obj: SSZType) -> Bytes32:
    return obj.hash_tree_root()


def uint_to_bytes(n: Uint) -> bytes:
    return serialize(n)


# Helper method for typing copies, and avoiding a example_input.copy() method call, instead of copy(example_input)
def copy[V: SSZType](obj: V) -> V:
    return obj.copy()
