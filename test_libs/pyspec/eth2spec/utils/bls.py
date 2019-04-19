from py_ecc import bls
from .ssz.ssz_impl import signing_root

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48


def only_with_bls(alt_return=None):
    """
    Decorator factory to make a function only run when BLS is active. Otherwise return the default.
    """
    def runner(fn):
        def entry(*args, **kw):
            if bls_active:
                return fn(*args, **kw)
            else:
                return alt_return
        return entry
    return runner


@only_with_bls(alt_return=True)
def bls_verify(pubkey, self_signed_object, signature, domain):
    return bls.verify(message_hash=signing_root(self_signed_object), pubkey=pubkey,
                      signature=signature, domain=int.from_bytes(domain, 'little'))


@only_with_bls(alt_return=True)
def bls_verify_multiple(pubkeys, roots, signature, domain):
    return bls.verify_multiple(pubkeys, roots, signature, int.from_bytes(domain, 'little'))


@only_with_bls(alt_return=STUB_PUBKEY)
def bls_aggregate_pubkeys(pubkeys):
    return bls.aggregate_pubkeys(pubkeys)


@only_with_bls(alt_return=STUB_SIGNATURE)
def bls_aggregate_signatures(signatures):
    return bls.aggregate_signatures(signatures)


@only_with_bls(alt_return=STUB_SIGNATURE)
def bls_sign(message_hash, privkey, domain):
    return bls.sign(message_hash=message_hash, privkey=privkey, domain=domain)
