"""
XMSS utilities backed by py-lean-pq's leanXMSS.
"""

from functools import lru_cache
from hashlib import sha256

import py_lean_pq as leanpq

################################################################################
# Constants
################################################################################

PUBKEY_SIZE = 32
SIGNATURE_SIZE = 2404
SEED_SIZE = 32
# A signature starts with its leaf index, little-endian
LEAF_INDEX_SIZE = 4

STUB_SIGNATURE = b"\x11" * SIGNATURE_SIZE

################################################################################
# Decorators
################################################################################

# Flag to make XMSS active or not. Used for testing, do not ignore XMSS in
# production unless you know what you are doing.
xmss_active = True


def only_with_xmss(alt_return=None):
    """
    Decorator factory to make a function only run when XMSS is active.
    Otherwise return the default.
    """

    def runner(fn):
        def entry(*args, **kw):
            if xmss_active:
                return fn(*args, **kw)
            else:
                return alt_return

        return entry

    return runner


################################################################################
# Helpers
################################################################################


def _sk_to_seed(SK):
    """
    Convert a secret key ``SK`` (int or bytes) to a leanXMSS seed.
    """
    if isinstance(SK, int):
        return SK.to_bytes(SEED_SIZE, "big")
    return bytes(SK)


@lru_cache(maxsize=256)
def _secret_key(seed):
    """
    The leanXMSS key grown from ``seed``. Keys are kept, since a key builds its
    top tree when it is created and the bottom tree of a leaf when it first
    signs there.
    """
    return leanpq.XmssSecretKey.from_seed(seed)


def _verify(PK, leaf_index, message, signature):
    """
    Verify one signature, including the leaf index it carries.
    """
    try:
        if GetLeafIndex(signature) != leaf_index:
            return False
        leanpq.xmss_verify(bytes(PK), bytes(message), bytes(signature))
        return True
    except (TypeError, ValueError, OverflowError, leanpq.LeanPqError):
        return False


################################################################################
# Keys
################################################################################


def StubPk(SK):
    """
    A placeholder public key for ``SK``, distinct for each key but not one
    that ``SK`` can sign for.
    """
    return sha256(b"XMSS stub pubkey" + _sk_to_seed(SK)).digest()


def SkToPk(SK):
    """
    The public key of ``SK``. When XMSS is inactive, ``StubPk`` is returned
    instead.
    """
    if not xmss_active:
        return StubPk(SK)
    return _secret_key(_sk_to_seed(SK)).public_key


################################################################################
# Signatures
################################################################################


def Sign(SK, leaf_index, message):
    if not xmss_active:
        # Like a real signature, the stub starts with its leaf index
        leaf_bytes = int(leaf_index).to_bytes(LEAF_INDEX_SIZE, "little")
        return leaf_bytes + STUB_SIGNATURE[LEAF_INDEX_SIZE:]
    return _secret_key(_sk_to_seed(SK)).sign(bytes(message), int(leaf_index))


@only_with_xmss(alt_return=True)
def Verify(PK, leaf_index, message, signature):
    return _verify(PK, int(leaf_index), message, signature)


def GetLeafIndex(signature):
    signature = bytes(signature)
    if len(signature) != SIGNATURE_SIZE:
        raise ValueError(f"signature: expected {SIGNATURE_SIZE} bytes, got {len(signature)}")
    return int.from_bytes(signature[:LEAF_INDEX_SIZE], "little")
