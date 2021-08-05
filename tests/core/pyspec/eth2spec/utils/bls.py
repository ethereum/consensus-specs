from py_ecc.bls import G2ProofOfPossession as py_ecc_bls
from py_ecc.bls.g2_primatives import signature_to_G2 as _signature_to_G2
import milagro_bls_binding as milagro_bls  # noqa: F401 for BLS switching option

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

# To change bls implementation, default to PyECC for correctness. Milagro is a good faster alternative.
bls = py_ecc_bls

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48
G2_POINT_AT_INFINITY = b'\xc0' + b'\x00' * 95
STUB_COORDINATES = _signature_to_G2(G2_POINT_AT_INFINITY)


def use_milagro():
    """
    Shortcut to use Milagro as BLS library
    """
    global bls
    bls = milagro_bls


def use_py_ecc():
    """
    Shortcut to use Py-ecc as BLS library
    """
    global bls
    bls = py_ecc_bls


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
    try:
        result = bls.Verify(PK, message, signature)
    except Exception:
        result = False
    finally:
        return result


@only_with_bls(alt_return=True)
def AggregateVerify(pubkeys, messages, signature):
    try:
        result = bls.AggregateVerify(list(pubkeys), list(messages), signature)
    except Exception:
        result = False
    finally:
        return result


@only_with_bls(alt_return=True)
def FastAggregateVerify(pubkeys, message, signature):
    try:
        result = bls.FastAggregateVerify(list(pubkeys), message, signature)
    except Exception:
        result = False
    finally:
        return result


@only_with_bls(alt_return=STUB_SIGNATURE)
def Aggregate(signatures):
    return bls.Aggregate(signatures)


@only_with_bls(alt_return=STUB_SIGNATURE)
def Sign(SK, message):
    if bls == py_ecc_bls:
        return bls.Sign(SK, message)
    else:
        return bls.Sign(SK.to_bytes(32, 'big'), message)


@only_with_bls(alt_return=STUB_COORDINATES)
def signature_to_G2(signature):
    return _signature_to_G2(signature)


@only_with_bls(alt_return=STUB_PUBKEY)
def AggregatePKs(pubkeys):
    if bls == py_ecc_bls:
        assert all(bls.KeyValidate(pubkey) for pubkey in pubkeys)
    elif bls == milagro_bls:
        # milagro_bls._AggregatePKs checks KeyValidate internally
        pass

    return bls._AggregatePKs(list(pubkeys))


@only_with_bls(alt_return=STUB_SIGNATURE)
def SkToPk(SK):
    if bls == py_ecc_bls:
        return bls.SkToPk(SK)
    else:
        return bls.SkToPk(SK.to_bytes(32, 'big'))
