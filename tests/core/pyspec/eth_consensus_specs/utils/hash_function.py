from hashlib import sha256

from eth_consensus_specs.utils.ssz.bytes import Bytes32

ZERO_BYTES32 = b"\x00" * 32


def hash(x: bytes | bytearray | memoryview) -> Bytes32:
    return Bytes32(sha256(x).digest())
