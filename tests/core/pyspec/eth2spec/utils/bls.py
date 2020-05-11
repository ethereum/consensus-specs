from py_ecc.bls import G2ProofOfPossession as py_ecc_bls
from py_ecc.bls.g2_primatives import signature_to_G2 as _signature_to_G2
import milagro_bls_binding as milagro_bls  # noqa: F401 for BLS switching option

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

# To change bls implementation, default to PyECC for correctness. Milagro is a good faster alternative.
bls = py_ecc_bls

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48
STUB_COORDINATES = _signature_to_G2(bls.Sign(0, b""))


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
def Verify(PK, message, signature):
    return bls.Verify(PK, message, signature)


@only_with_bls(alt_return=True)
def AggregateVerify(pairs, signature):
    return bls.AggregateVerify(list(pairs), signature)


@only_with_bls(alt_return=True)
def FastAggregateVerify(PKs, message, signature):
    return bls.FastAggregateVerify(list(PKs), message, signature)


@only_with_bls(alt_return=STUB_SIGNATURE)
def Aggregate(signatures):
    return bls.Aggregate(signatures)


@only_with_bls(alt_return=STUB_SIGNATURE)
def Sign(SK, message):
    if bls == py_ecc_bls:
        return bls.Sign(SK, message)
    else:
        return bls.Sign(SK.to_bytes(48, 'big'), message)


@only_with_bls(alt_return=STUB_COORDINATES)
def signature_to_G2(signature):
    return _signature_to_G2(signature)


@only_with_bls(alt_return=STUB_PUBKEY)
def AggregatePKs(pubkeys):
    return bls._AggregatePKs(list(pubkeys))
