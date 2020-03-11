from remerkleable.core import View
from remerkleable.byte_arrays import Bytes32


def serialize(obj: View) -> bytes:
    return obj.encode_bytes()


def hash_tree_root(obj: View) -> Bytes32:
    return Bytes32(obj.get_backing().merkle_root())
