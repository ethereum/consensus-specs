import pytest
from .merkle_minimal import zerohashes, merkleize_chunks, get_merkle_root
from .hash_function import hash


def h(a: bytes, b: bytes) -> bytes:
    return hash(a + b)


def e(v: int) -> bytes:
    return v.to_bytes(length=32, byteorder='little')


def z(i: int) -> bytes:
    return zerohashes[i]


cases = [
    (0, 0, 1, z(0)),
    (0, 1, 1, e(0)),
    (1, 0, 2, h(z(0), z(0))),
    (1, 1, 2, h(e(0), z(0))),
    (1, 2, 2, h(e(0), e(1))),
    (2, 0, 4, h(h(z(0), z(0)), z(1))),
    (2, 1, 4, h(h(e(0), z(0)), z(1))),
    (2, 2, 4, h(h(e(0), e(1)), z(1))),
    (2, 3, 4, h(h(e(0), e(1)), h(e(2), z(0)))),
    (2, 4, 4, h(h(e(0), e(1)), h(e(2), e(3)))),
    (3, 0, 8, h(h(h(z(0), z(0)), z(1)), z(2))),
    (3, 1, 8, h(h(h(e(0), z(0)), z(1)), z(2))),
    (3, 2, 8, h(h(h(e(0), e(1)), z(1)), z(2))),
    (3, 3, 8, h(h(h(e(0), e(1)), h(e(2), z(0))), z(2))),
    (3, 4, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), z(2))),
    (3, 5, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), z(0)), z(1)))),
    (3, 6, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(z(0), z(0))))),
    (3, 7, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), z(0))))),
    (3, 8, 8, h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), e(7))))),
    (4, 0, 16, h(h(h(h(z(0), z(0)), z(1)), z(2)), z(3))),
    (4, 1, 16, h(h(h(h(e(0), z(0)), z(1)), z(2)), z(3))),
    (4, 2, 16, h(h(h(h(e(0), e(1)), z(1)), z(2)), z(3))),
    (4, 3, 16, h(h(h(h(e(0), e(1)), h(e(2), z(0))), z(2)), z(3))),
    (4, 4, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), z(2)), z(3))),
    (4, 5, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), z(0)), z(1))), z(3))),
    (4, 6, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(z(0), z(0)))), z(3))),
    (4, 7, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), z(0)))), z(3))),
    (4, 8, 16, h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), e(7)))), z(3))),
    (4, 9, 16,
     h(h(h(h(e(0), e(1)), h(e(2), e(3))), h(h(e(4), e(5)), h(e(6), e(7)))), h(h(h(e(8), z(0)), z(1)), z(2)))),
]


@pytest.mark.parametrize(
    'depth,count,pow2,value',
    cases,
)
def test_merkleize_chunks_and_get_merkle_root(depth, count, pow2, value):
    chunks = [e(i) for i in range(count)]
    assert merkleize_chunks(chunks, pad_to=pow2) == value
    assert get_merkle_root(chunks, pad_to=pow2) == value
