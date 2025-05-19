from hashlib import sha256
from typing import Union

from remerkleable.byte_arrays import Bytes32

ZERO_BYTES32 = b"\x00" * 32


def hash(x: Union[bytes, bytearray, memoryview]) -> Bytes32:
    return Bytes32(sha256(x).digest())
