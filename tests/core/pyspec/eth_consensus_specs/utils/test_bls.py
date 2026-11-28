import pytest

from .bls import (
    bytes48_to_G1,
    bytes96_to_G2,
    G1,
    G2,
    G2_POINT_AT_INFINITY,
    KeyValidate,
    Sign,
    SkToPk,
    Verify,
)

G1_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 47

# Infinity flag set, but the remaining bits are not all zero.
NON_CANONICAL_G1_INFINITY = [
    b"\xc0" + b"\x00" * 46 + b"\x01",
    b"\xe0" + b"\x00" * 47,
    b"\xc0" + b"\xff" * 47,
]
NON_CANONICAL_G2_INFINITY = [
    b"\xc0" + b"\x00" * 94 + b"\x01",
    b"\xe0" + b"\x00" * 95,
    b"\xc0" + b"\xff" * 95,
]
INFINITY_IDS = ["nonzero_x", "sign_bit", "all_ones"]


def test_canonical_infinity_is_deserialized():
    assert bytes48_to_G1(G1_POINT_AT_INFINITY) == G1.identity()
    assert bytes96_to_G2(G2_POINT_AT_INFINITY) == G2.identity()


@pytest.mark.parametrize("encoding", NON_CANONICAL_G1_INFINITY, ids=INFINITY_IDS)
def test_non_canonical_g1_infinity_is_rejected(encoding):
    with pytest.raises(ValueError, match="non-canonical"):
        bytes48_to_G1(encoding)
    assert not KeyValidate(encoding)


@pytest.mark.parametrize("encoding", NON_CANONICAL_G2_INFINITY, ids=INFINITY_IDS)
def test_non_canonical_g2_infinity_is_rejected(encoding):
    with pytest.raises(ValueError, match="non-canonical"):
        bytes96_to_G2(encoding)
    assert not Verify(SkToPk(1), b"message", encoding)


def test_valid_pubkey_and_signature():
    pubkey = SkToPk(1)
    signature = Sign(1, b"message")
    assert KeyValidate(pubkey)
    assert Verify(pubkey, b"message", signature)
    assert bytes48_to_G1(pubkey).to_compressed_bytes() == pubkey
    assert bytes96_to_G2(signature).to_compressed_bytes() == signature
