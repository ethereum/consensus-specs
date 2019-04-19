from typing import List, Any
from eth2spec.phase0.data_types import *


def bls_verify(pubkey: Bytes48, self_signed_object: Any, domain: Bytes8) -> bool:
    return True


def bls_verify_multiple(pubkeys: List[Bytes48], roots: List[Bytes32], signature: Bytes96, domain: Bytes8) -> bool:
    return True


def bls_aggregate_pubkeys(pubkeys: List[Bytes48]):
    return b'\x42' * 96
