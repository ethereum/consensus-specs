from hashlib import sha256
from typing import Dict, Union

ZERO_BYTES32 = b'\x00' * 32


def _hash(x: Union[bytes, bytearray, memoryview]) -> bytes:
    return sha256(x).digest()


hash_cache: Dict[bytes, bytes] = {}


def hash(x: bytes) -> bytes:
    if x in hash_cache:
        return hash_cache[x]
    return _hash(x)
