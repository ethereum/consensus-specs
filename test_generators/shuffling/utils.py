from eth_typing import Hash32
from eth_utils import keccak


def hash(x: bytes) -> Hash32:
    return keccak(x)
