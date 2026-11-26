"""
Execution-layer primitives backed by the rlp library.
"""

from collections.abc import Iterable

import rlp
from ssz.byte_arrays import ByteList
from ssz.uint import Uint8


def _is_byte_string(value: object) -> bool:
    """
    Return whether ``value`` is bytes, including SSZ lists of bytes.
    """
    if isinstance(value, (bytes, bytearray, ByteList)):
        return True
    element_type = getattr(type(value), "ELEMENT_TYPE", None)
    return isinstance(element_type, type) and issubclass(element_type, Uint8)


def _to_rlp_value(value: object) -> object:
    """
    Convert ``value`` into the ints, bytes, and lists that ``rlp`` encodes.
    """
    if isinstance(value, int):
        return int(value)
    if _is_byte_string(value):
        return bytes(value)
    assert isinstance(value, Iterable)
    return [_to_rlp_value(item) for item in value]


def rlp_encode(value: object) -> bytes:
    """
    Return the RLP encoding of ``value``, where integers are encoded as
    big-endian scalars, bytes as strings, and sequences as lists.
    """
    return rlp.encode(_to_rlp_value(value))
