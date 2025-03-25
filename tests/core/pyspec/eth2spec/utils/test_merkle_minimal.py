import pytest
from .merkle_minimal import zerohashes, merkleize_chunks, get_merkle_root
from .hash_function import hash


def h(a: bytes, b: bytes) -> bytes:
    return hash(a + b)


def e(v: int) -> bytes:
    # prefix with 0xfff... to make it non-zero
    return b"\xff" * 28 + v.to_bytes(length=4, byteorder="little")


def z(i: int) -> bytes:
    return zerohashes[i]


cases = [
    # limit 0: always zero hash
    (0, 0, z(0)),
    (1, 0, None),  # cut-off due to limit
    (2, 0, None),  # cut-off due to limit
    # limit 1: padded to 1 element if not already. Returned (like identity func)
    (0, 1, z(0)),
    (1, 1, e(0)),
    (2, 1, None),  # cut-off due to limit
    (1, 1, e(0)),
    (0, 2, h(z(0), z(0))),
    (1, 2, h(e(0), z(0))),
    (2, 2, h(e(0), e(1))),
    (3, 2, None),  # cut-off due to limit
    (16, 2, None),  # bigger cut-off due to limit
    (0, 4, h(h(z(0), z(0)), z(1))),
    (1, 4, h(h(e(0), z(0)), z(1))),
    (2, 4, h(h(e(0), e(1)), z(1))),
    (3, 4, h(h(e(0), e(1)), h(e(2), z(0)))),
    (4, 4, h(h(e(0), e(1)), h(e(2), e(3)))),
    (5, 4, None),  # cut-off due to limit
    (0, 8, h(h(h(z(0), z(0)), z(1)), z(2))),
    (1, 8, h(h(h(e(0), z(0)), z(1)), z(2))),
    (2, 8, h(h(h(e(0), e(1)), z(1)), z(2))),
    (3, 8, h(h(h(e(0), e(1)), h(e(2), z(0))), z(2))),
    (4, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), z(2))),
    (5, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), z(0)), z(1)))),
    (6, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(z(0), z(0))))),
    (7, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), z(0))))),
    (8, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), e(7))))),
    (9, 8, None),  # cut-off due to limit
    (0, 16, h(h(h(h(z(0), z(0)), z(1)), z(2)), z(3))),
    (1, 16, h(h(h(h(e(0), z(0)), z(1)), z(2)), z(3))),
    (2, 16, h(h(h(h(e(0), e(1)), z(1)), z(2)), z(3))),
    (3, 16, h(h(h(h(e(0), e(1)), h(e(2), z(0))), z(2)), z(3))),
    (4, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), z(2)), z(3))),
    (5, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), z(0)), z(1))), z(3))),
    (
        6,
        16,
        h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(z(0), z(0)))), z(3)),
    ),
    (
        7,
        16,
        h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), z(0)))), z(3)),
    ),
    (
        8,
        16,
        h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), e(7)))), z(3)),
    ),
    (
        9,
        16,
        h(
            h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), e(7)))),
            h(h(h(e(8), z(0)), z(1)), z(2)),
        ),
    ),
]


@pytest.mark.parametrize(
    "count,limit,value",
    cases,
)
def test_merkleize_chunks_and_get_merkle_root(count, limit, value):
    chunks = [e(i) for i in range(count)]
    if value is None:
        bad = False
        try:
            merkleize_chunks(chunks, limit=limit)
            bad = True
        except AssertionError:
            pass
        if bad:
            assert False, "expected merkleization to be invalid"
    else:
        assert merkleize_chunks(chunks, limit=limit) == value
        assert get_merkle_root(chunks, pad_to=limit) == value
