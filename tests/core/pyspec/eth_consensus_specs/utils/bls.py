"""
BLS12-381 utilities backed by py_arkworks_bls12381.
"""

from py_arkworks_bls12381 import G1Point as G1, G2Point as G2, GT, Scalar

################################################################################
# Constants
################################################################################

STUB_SIGNATURE = b"\x11" * 96
STUB_PUBKEY = b"\x22" * 48
G2_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 95

################################################################################
# Decorators
################################################################################

# Flag to make BLS active or not. Used for testing, do not ignore BLS in
# production unless you know what you are doing.
bls_active = True


def only_with_bls(alt_return=None):
    """
    Decorator factory to make a function only run when BLS is active.
    Otherwise return the default.
    """

    def runner(fn):
        def entry(*args, **kw):
            if bls_active:
                return fn(*args, **kw)
            else:
                return alt_return

        return entry

    return runner


################################################################################
# Helpers
################################################################################


def _hash_to_G2(message):
    """
    Hash `message` to a point in G2 using the BLS signature ciphersuite.
    """
    return G2.hash_to_curve(message, b"BLS_SIG_BLS12381G2_XMD:SHA-256_SSWU_RO_POP_")


def _pubkey_to_point(pubkey):
    """
    Deserialize `pubkey` to a G1 point, or `None` if the encoding is invalid.
    """
    try:
        return G1.from_compressed_bytes_unchecked(pubkey)
    except Exception:
        return None


def _signature_to_point(signature):
    """
    Deserialize `signature` to a G2 point, or `None` if the encoding is invalid.
    """
    try:
        return G2.from_compressed_bytes_unchecked(signature)
    except Exception:
        return None


def _sk_to_scalar(SK):
    """
    Convert a secret key `SK` (int or big-endian bytes) to a scalar.
    """
    if isinstance(SK, (bytes, bytearray)):
        SK = int.from_bytes(SK, "big")
    return Scalar(SK)


def _valid_pubkey_point(pubkey):
    """
    Return the G1 point for `pubkey` if it passes KeyValidate, else `None`.
    """
    point = _pubkey_to_point(pubkey)
    if point is None or point == G1.identity() or not point.is_in_subgroup():
        return None
    return point


def _valid_signature_point(signature):
    """
    Return the G2 point for `signature` if it is a valid subgroup member, else `None`.
    """
    point = _signature_to_point(signature)
    if point is None or not point.is_in_subgroup():
        return None
    return point


def _aggregate_pubkey_points(pubkeys):
    """
    Aggregate `pubkeys` into a single G1 point, or `None` if empty or any is invalid.
    """
    aggregate = None
    for pubkey in pubkeys:
        point = _valid_pubkey_point(pubkey)
        if point is None:
            return None
        aggregate = point if aggregate is None else aggregate + point
    return aggregate


################################################################################
# Signatures
################################################################################


@only_with_bls(alt_return=True)
def Verify(PK, message, signature):
    pubkey_point = _valid_pubkey_point(PK)
    if pubkey_point is None:
        return False
    signature_point = _valid_signature_point(signature)
    if signature_point is None:
        return False
    message_point = _hash_to_G2(message)
    # e(PK, H(m)) == e(G1, signature)  <=>  e(-G1, signature) * e(PK, H(m)) == 1
    return GT.pairing_check([-G1(), pubkey_point], [signature_point, message_point])


@only_with_bls(alt_return=True)
def AggregateVerify(pubkeys, messages, signature):
    pubkeys = list(pubkeys)
    messages = list(messages)
    if len(pubkeys) == 0 or len(pubkeys) != len(messages):
        return False
    signature_point = _valid_signature_point(signature)
    if signature_point is None:
        return False
    g1_points = []
    g2_points = []
    for pubkey, message in zip(pubkeys, messages, strict=True):
        pubkey_point = _valid_pubkey_point(pubkey)
        if pubkey_point is None:
            return False
        g1_points.append(pubkey_point)
        g2_points.append(_hash_to_G2(message))
    g1_points.append(-G1())
    g2_points.append(signature_point)
    # prod_i e(PK_i, H(m_i)) == e(G1, signature) <=> (prod_i e(PK_i, H(m_i))) * e(-G1, signature) = 1
    return GT.pairing_check(g1_points, g2_points)


@only_with_bls(alt_return=True)
def FastAggregateVerify(pubkeys, message, signature):
    aggregate = _aggregate_pubkey_points(pubkeys)
    if aggregate is None:
        return False
    signature_point = _valid_signature_point(signature)
    if signature_point is None:
        return False
    message_point = _hash_to_G2(message)
    # e(G1, signature) = e(aggregate, H(m)) <=> e(-G1, signature) * e(aggregate, H(m)) = 1
    return GT.pairing_check([-G1(), aggregate], [signature_point, message_point])


@only_with_bls(alt_return=STUB_SIGNATURE)
def Aggregate(signatures):
    assert len(signatures) > 0
    aggregate = None
    for signature in signatures:
        point = _signature_to_point(signature)
        if point is None:
            raise Exception(f"invalid signature encoding: {signature!r}")
        aggregate = point if aggregate is None else aggregate + point
    return aggregate.to_compressed_bytes()


@only_with_bls(alt_return=STUB_SIGNATURE)
def Sign(SK, message):
    signature_point = _hash_to_G2(message) * _sk_to_scalar(SK)
    return signature_point.to_compressed_bytes()


@only_with_bls(alt_return=STUB_PUBKEY)
def AggregatePKs(pubkeys):
    aggregate = _aggregate_pubkey_points(pubkeys)
    assert aggregate is not None, f"empty or invalid pubkeys: {pubkeys!r}"
    return aggregate.to_compressed_bytes()


@only_with_bls(alt_return=STUB_SIGNATURE)
def SkToPk(SK):
    pubkey_point = G1() * _sk_to_scalar(SK)
    return pubkey_point.to_compressed_bytes()


@only_with_bls(alt_return=True)
def KeyValidate(pubkey):
    return _valid_pubkey_point(pubkey) is not None


################################################################################
# Operations
################################################################################


def add(lhs, rhs):
    """
    Performs point addition of `lhs` and `rhs`.
    The points can either be in G1 or G2.
    """
    return lhs + rhs


def multiply(point, scalar):
    """
    Performs scalar multiplication of `point` and `scalar`.
    The points can either be in G1 or G2.
    """
    return point * scalar


def multi_exp(points, scalars):
    """
    Performs a multi-scalar multiplication of `points` and `scalars`.
    The points can either be in G1 or G2.
    """
    # Since this method accepts either G1 or G2, we need to know
    # the type of the point to return. Hence, we need at least one point.
    if not points or not scalars:
        raise Exception("Cannot call multi_exp with zero points or zero scalars")

    # Check if we need to perform a G1 or G2 multiexp
    if isinstance(points[0], G1):
        return G1.multiexp_unchecked(points, scalars)
    elif isinstance(points[0], G2):
        return G2.multiexp_unchecked(points, scalars)
    else:
        raise Exception("Invalid point type")


def neg(point):
    """
    Returns the point negation of `point`.
    The point can either be in G1 or G2.
    """
    return -point


################################################################################
# Serialization
################################################################################


def G1_to_bytes48(point):
    """
    Serializes a point in G1.
    """
    return point.to_compressed_bytes()


def G2_to_bytes96(point):
    """
    Serializes a point in G2.
    """
    return point.to_compressed_bytes()


def bytes48_to_G1(bytes48):
    """
    Deserializes a purported compressed serialized point in G1.
        - No subgroup checks are performed.
        - If the bytearray is not a valid serialization
          of a point in G1, then this method will raise
          an exception.
    """
    return G1.from_compressed_bytes_unchecked(bytes48)


def bytes96_to_G2(bytes96):
    """
    Deserializes a purported compressed serialized point in G2.
        - No subgroup checks are performed.
        - If the bytearray is not a valid serialization
          of a point in G2, then this method will raise
          an exception.
    """
    return G2.from_compressed_bytes_unchecked(bytes96)
