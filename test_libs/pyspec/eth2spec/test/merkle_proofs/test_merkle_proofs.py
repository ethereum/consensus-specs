import re
from eth_utils import (
    to_tuple,
)

from eth2spec.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_all_phases_except,
)
from eth2spec.utils.ssz.ssz_typing import (
    Bytes32,
    Container,
    List,
    uint64,
)


class Foo(Container):
    x: uint64
    y: List[Bytes32, 2]

# Tree
#      root
#     /    \
#    x    y_root
#         /    \
# y_data_root  len(y)
#      /  \
#    / \ / \
#
# Generalized indices
#           1
#          / \
#      2 (x)    3 (y_root)
#                / \
#              6     7
#             / \
#           12  13


@to_tuple
def ssz_object_to_path(start, end):
    is_len = False
    len_findall = re.findall(r"(?<=len\().*(?=\))", end)
    if len_findall:
        is_len = True
        end = len_findall[0]

    route = ''
    if end.startswith(start):
        route = end[len(start):]

    segments = route.split('.')
    for word in segments:
        index_match = re.match(r"(\w+)\[(\d+)]", word)
        if index_match:
            yield from index_match.groups()
        elif len(word):
            yield word
    if is_len:
        yield '__len__'


to_path_test_cases = [
    ('foo', 'foo.x', ('x',)),
    ('foo', 'foo.x[100].y', ('x', '100', 'y')),
    ('foo', 'foo.x[100].y[1].z[2]', ('x', '100', 'y', '1', 'z', '2')),
    ('foo', 'len(foo.x[100].y[1].z[2])', ('x', '100', 'y', '1', 'z', '2', '__len__')),
]


def test_to_path():
    for test_case in to_path_test_cases:
        start, end, expected = test_case
        assert ssz_object_to_path(start, end) == expected


generalized_index_cases = [
    (Foo, ('x',), 2),
    (Foo, ('y',), 3),
    (Foo, ('y', 0), 12),
    (Foo, ('y', 1), 13),
    (Foo, ('y', '__len__'), None),
]


@with_all_phases_except(['phase0'])
@spec_state_test
def test_get_generalized_index(spec, state):
    for typ, path, generalized_index in generalized_index_cases:
        if generalized_index is not None:
            assert spec.get_generalized_index(
                typ=typ,
                path=path,
            ) == generalized_index
        else:
            expect_assertion_error(lambda: spec.get_generalized_index(typ=typ, path=path))

        yield 'typ', typ
        yield 'path', path
        yield 'generalized_index', generalized_index


@with_all_phases_except(['phase0'])
@spec_state_test
def test_verify_merkle_proof(spec, state):
    h = spec.hash
    a = b'\x11' * 32
    b = b'\x22' * 32
    c = b'\x33' * 32
    d = b'\x44' * 32
    root = h(h(a + b) + h(c + d))
    leaf = a
    generalized_index = 4
    proof = [b, h(c + d)]

    is_valid = spec.verify_merkle_proof(
        leaf=leaf,
        proof=proof,
        index=generalized_index,
        root=root,
    )
    assert is_valid

    yield 'proof', proof
    yield 'is_valid', is_valid


@with_all_phases_except(['phase0'])
@spec_state_test
def test_verify_merkle_multiproof(spec, state):
    h = spec.hash
    a = b'\x11' * 32
    b = b'\x22' * 32
    c = b'\x33' * 32
    d = b'\x44' * 32
    root = h(h(a + b) + h(c + d))
    leaves = [a, d]
    generalized_indices = [4, 7]
    proof = [c, b]  # helper_indices = [6, 5]

    is_valid = spec.verify_merkle_multiproof(
        leaves=leaves,
        proof=proof,
        indices=generalized_indices,
        root=root,
    )
    assert is_valid

    yield 'proof', proof
    yield 'is_valid', is_valid
