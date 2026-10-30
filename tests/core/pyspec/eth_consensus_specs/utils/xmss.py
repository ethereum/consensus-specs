"""
leanXMSS utilities backed by py-lean-pq.

Signature verification and signing follow the BLS setting: when BLS is inactive,
verification passes and signing returns a stub signature at the requested leaf
index. Public keys are always derived, since they are data written into the
beacon state.
"""

from functools import cache

import py_lean_pq

from eth_consensus_specs.utils import bls
from eth_consensus_specs.utils.bls import only_with_bls

XMSS_SIGNATURE_SIZE = 2404


@cache
def _secret_key(secret_key: bytes) -> py_lean_pq.XmssSecretKey:
    # Key generation builds the top tree, and the first signature in each bottom
    # tree builds that tree, so keys are kept for reuse across tests.
    return py_lean_pq.XmssSecretKey.from_seed(secret_key)


def _stub_signature(index: int) -> bytes:
    return int(index).to_bytes(4, "little") + b"\x11" * (XMSS_SIGNATURE_SIZE - 4)


@only_with_bls(alt_return=True)
def Verify(public_key, message, signature):
    try:
        py_lean_pq.xmss_verify(bytes(public_key), bytes(message), bytes(signature))
    except (py_lean_pq.LeanPqError, ValueError):
        return False
    return True


def Sign(secret_key, message, index):
    if not bls.bls_active:
        return _stub_signature(index)
    return bytes(_secret_key(bytes(secret_key)).sign(bytes(message), int(index)))


def SkToPk(secret_key):
    return bytes(_secret_key(bytes(secret_key)).public_key)
