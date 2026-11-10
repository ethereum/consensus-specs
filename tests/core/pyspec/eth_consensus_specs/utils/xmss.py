"""
XMSS utilities backed by ethlib's leanXMSS.
"""

from hashlib import sha256

from ethlib.cryptography import xmss as leanxmss

################################################################################
# Constants
################################################################################

PUBKEY_SIZE = leanxmss.PUB_KEY_SIZE
SIGNATURE_SIZE = leanxmss.SIG_SIZE
SEED_SIZE = leanxmss.SEED_LEN

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


def _verify(PK, leaf_index, message, signature):
    """
    Verify one signature, including the leaf index it carries.
    """
    try:
        if leanxmss.signature_index(bytes(signature)) != leaf_index:
            return False
        return leanxmss.verify(bytes(PK), bytes(message), bytes(signature))
    except (TypeError, ValueError, OverflowError, RuntimeError):
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
    The public key of ``SK``.

    Key generation builds the key's top tree and takes minutes. When XMSS is
    inactive, ``StubPk`` is returned instead.
    """
    if not xmss_active:
        return StubPk(SK)
    return leanxmss.key_gen(_sk_to_seed(SK))


################################################################################
# Signatures
################################################################################


@only_with_xmss(alt_return=STUB_SIGNATURE)
def Sign(SK, leaf_index, message):
    return leanxmss.sign(_sk_to_seed(SK), int(leaf_index), bytes(message))


@only_with_xmss(alt_return=True)
def Verify(PK, leaf_index, message, signature):
    return _verify(PK, int(leaf_index), message, signature)
