# flake8:noqa F401  Ignore unused imports. Tests are a work in progress.
import pytest

from random import Random

from remerkleable.core import View, TypeDef, BasicView
from remerkleable.complex import Container, Vector, List
from remerkleable.basic import boolean, bit, uint, byte, uint8, uint16, uint32, uint64, uint128, uint256,\
    OperationNotSupported
from remerkleable.bitfields import Bitvector, Bitlist
from remerkleable.byte_arrays import ByteVector, Bytes1, Bytes4, Bytes8, Bytes32, Bytes48, Bytes96
from remerkleable.core import BasicView, View, TypeDef
from remerkleable.tree import get_depth


def expect_op_error(fn, msg):
    try:
        fn()
        raise AssertionError(msg)
    except (ValueError, OperationNotSupported, AttributeError) as e:
        pass


def test_subclasses():
    for u in [uint8, uint16, uint32, uint64, uint128, uint256]:
        assert issubclass(u, int)
        assert issubclass(u, View)
        assert issubclass(u, BasicView)
        assert isinstance(u, TypeDef)
    assert issubclass(boolean, BasicView)
    assert issubclass(boolean, View)
    assert isinstance(boolean, TypeDef)

    for c in [Container, List, Vector, Bytes32]:
        assert issubclass(c, View)
        assert isinstance(c, TypeDef)


def test_basic_instances():
    for u in [uint8, byte, uint16, uint32, uint64, uint128, uint256]:
        v = u(123)
        assert isinstance(v, int)
        assert isinstance(v, BasicView)
        assert isinstance(v, View)

    assert isinstance(boolean(True), BasicView)
    assert isinstance(boolean(False), BasicView)
    assert isinstance(bit(True), boolean)
    assert isinstance(bit(False), boolean)


def test_basic_value_bounds():
    max = {
        boolean: 2 ** 1,
        bit: 2 ** 1,
        uint8: 2 ** (8 * 1),
        byte: 2 ** (8 * 1),
        uint16: 2 ** (8 * 2),
        uint32: 2 ** (8 * 4),
        uint64: 2 ** (8 * 8),
        uint128: 2 ** (8 * 16),
        uint256: 2 ** (8 * 32),
    }
    for k, v in max.items():
        # this should work
        assert k(v - 1) == v - 1
        # but we do not allow overflows
        expect_op_error(lambda: k(v), f"no overflows allowed: type: {k}, value: {v}")

    for k, _ in max.items():
        # this should work
        assert k(0) == 0
        # but we do not allow underflows
        expect_op_error(lambda: k(-1), "no underflows allowed")

    for k, v in max.items():
        if v == 2:
            continue  # skip bool/bit
        half = v // 2
        # this should work
        assert k(half) + k(half-1) == v - 1
        # but 2x half == max, so this should fail
        expect_op_error(lambda: k(half) + k(half), f"no __add__ overflows allowed: type: {k}, value: {half}")
        # this should work
        assert k(half) - k(half) == 0
        assert k(half-1) - k(half-1) == 0
        # but underflow should not
        expect_op_error(lambda: k(half - 1) - k(half), f"no __sub__ underflows allowed: type: {k}, value: {half}")

    for k, v in max.items():
        if v == 2:
            continue  # skip bool/bit
        assert k(v-1) * k(1) == v-1
        assert k(v // 3) * 2 == (v // 3) * 2
        assert k((v // 2) - 1) * 2 == ((v // 2) - 1) * 2
        # but 2x max-1 should fail
        expect_op_error(lambda: k(v - 1) * 2, f"no __mul__ overflows allowed: type: {k}")
        # and 2x half too
        expect_op_error(lambda: k(v // 2) * 2, f"no __mul__ overflows allowed: type: {k}")
        expect_op_error(lambda: k(v // 2) // 0.5, f"no __floordiv__ with float overflows allowed: type: {k}")
        expect_op_error(lambda: k(v - 1) / 2.0, f"no __truediv__ allowed: type: {k}")


def test_container():
    class Foo(Container):
        a: uint8
        b: uint32

    empty = Foo()
    assert empty.a == uint8(0)
    assert empty.b == uint32(0)

    assert issubclass(Foo, Container)
    assert issubclass(Foo, View)

    assert Foo.is_fixed_byte_length()
    x = Foo(a=uint8(123), b=uint32(45))
    assert x.a == 123
    assert x.b == 45
    assert isinstance(x.a, uint8)
    assert isinstance(x.b, uint32)
    assert x.__class__.is_fixed_byte_length()

    class Bar(Container):
        a: uint8
        b: List[uint8, 1024]

    assert not Bar.is_fixed_byte_length()

    y = Bar(a=123, b=List[uint8, 1024](uint8(1), uint8(2)))
    assert y.a == 123
    assert isinstance(y.a, uint8)
    assert len(y.b) == 2
    assert isinstance(y.a, uint8)
    assert not y.__class__.is_fixed_byte_length()
    assert y.b[0] == 1
    v: List = y.b
    assert v.__class__.element_cls() == uint8
    assert v.__class__.limit() == 1024

    field_values = list(y)
    assert field_values == [y.a, y.b]

    f_a, f_b = y
    assert f_a == y.a
    assert f_b == y.b

    y.a = 42
    try:
        y.a = 256  # out of bounds
        assert False
    except ValueError:
        pass

    try:
        y.a = uint16(255)  # within bounds, wrong type
        assert False
    except ValueError:
        pass

    try:
        y.not_here = 5
        assert False
    except AttributeError:
        pass

    try:
        Foo(wrong_field_name=100)
        assert False
    except AttributeError:
        pass


def test_container_unpack():
    class Foo(Container):
        a: uint64
        b: uint8
        c: Vector[uint16, 123]

    foo = Foo(b=42)
    a, b, c = foo
    assert b == 42


def test_list():
    typ = List[uint64, 128]
    assert issubclass(typ, List)
    assert issubclass(typ, View)
    assert isinstance(typ, TypeDef)

    assert not typ.is_fixed_byte_length()

    assert len(typ()) == 0  # empty
    assert len(typ(uint64(0))) == 1  # single arg
    assert len(typ(uint64(i) for i in range(10))) == 10  # generator
    assert len(typ(uint64(0), uint64(1), uint64(2))) == 3  # args
    assert isinstance(typ(1, 2, 3, 4, 5)[4], uint64)  # coercion
    assert isinstance(typ(i for i in range(10))[9], uint64)  # coercion in generator

    v = typ(uint64(2), uint64(1))
    v[0] = uint64(123)
    assert v[0] == 123
    assert isinstance(v[0], uint64)

    assert isinstance(v, List)
    assert isinstance(v, View)

    assert len(typ([i for i in range(10)])) == 10  # cast py list to SSZ list

    foo = List[uint32, 128](0 for i in range(128))
    foo[0] = 123
    foo[1] = 654
    foo[127] = 222
    assert sum(foo) == 999
    try:
        foo[3] = 2 ** 32  # out of bounds
    except ValueError:
        pass

    for i in range(128):
        foo.pop()
        assert len(foo) == 128 - 1 - i
    for i in range(128):
        foo.append(uint32(i))
        assert len(foo) == i + 1
        assert foo[i] == i

    try:
        foo[3] = uint64(2 ** 32 - 1)  # within bounds, wrong type
        assert False
    except ValueError:
        pass

    try:
        foo[128] = 100
        assert False
    except IndexError:
        pass

    try:
        foo[-1] = 100  # valid in normal python lists
        assert False
    except IndexError:
        pass

    try:
        foo[128] = 100  # out of bounds
        assert False
    except IndexError:
        pass


def test_bytesn_subclass():
    class Root(Bytes32):
        pass

    assert isinstance(Root(b'\xab' * 32), Bytes32)
    assert not isinstance(Root(b'\xab' * 32), Bytes48)
    assert issubclass(Root(b'\xab' * 32).__class__, Bytes32)
    assert issubclass(Root, Bytes32)

    assert not issubclass(Bytes48, Bytes32)

    assert len(Bytes32() + Bytes48()) == 80


def test_uint_math():
    assert uint8(0) + uint8(uint32(16)) == uint8(16)  # allow explicit casting to make invalid addition valid

    expect_op_error(lambda: uint8(0) - uint8(1), "no underflows allowed")
    expect_op_error(lambda: uint8(1) + uint8(255), "no overflows allowed")
    expect_op_error(lambda: uint8(0) + 256, "no overflows allowed")
    expect_op_error(lambda: uint8(42) + uint32(123), "no mixed types")
    expect_op_error(lambda: uint32(42) + uint8(123), "no mixed types")

    assert type(uint32(1234) + 56) == uint32


def test_container_depth():
    class SingleField(Container):
        foo: uint32

    assert SingleField.tree_depth() == 0

    class TwoField(Container):
        foo: uint32
        bar: uint64

    assert TwoField.tree_depth() == 1

    class ThreeField(Container):
        foo: uint32
        bar: uint64
        quix: uint8

    assert ThreeField.tree_depth() == 2

    class FourField(Container):
        foo: uint32
        bar: uint64
        quix: uint8
        more: uint32

    assert FourField.tree_depth() == 2

    class FiveField(Container):
        foo: uint32
        bar: uint64
        quix: uint8
        more: uint32
        fiv: uint8

    assert FiveField.tree_depth() == 3


@pytest.mark.parametrize("count, depth", [
    (0, 0), (1, 0), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 3), (8, 3), (9, 4)])
def test_tree_depth(count: int, depth: int):
    assert get_depth(count) == depth


def test_paths():
    class FourField(Container):
        foo: uint32
        bar: uint64
        quix: uint8
        more: uint32

    assert (FourField / 'foo').navigate_type() == uint32
    assert (FourField / 'bar').navigate_type() == uint64
    assert (FourField / 'foo').gindex() == 0b100
    assert (FourField / 'bar').gindex() == 0b101

    class Wrapper(Container):
        a: uint32
        b: FourField

    assert (Wrapper / 'a').navigate_type() == uint32
    assert (Wrapper / 'b').navigate_type() == FourField
    assert (Wrapper / 'b' / 'quix').navigate_type() == uint8

    assert (Wrapper / 'a').gindex() == 0b10
    assert (Wrapper / 'b' / 'more').gindex() == 0b1111

    assert ((Wrapper / 'b') / (FourField / 'quix')).gindex() == ((Wrapper / 'b') / 'quix').gindex()

    w = Wrapper(b=FourField(quix=42))
    assert (Wrapper / 'b' / 'quix').navigate_view(w) == 42

    assert (List[uint32, 123] / 0).navigate_type() == uint32
    try:
        (List[uint32, 123] / 123).navigate_type()
        assert False
    except KeyError:
        pass


def test_bitvector():
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        for i in range(size):
            b = Bitvector[size]()
            b[i] = True
            assert bool(b[i]) == True, "set %d / %d" % (i, size)

        for i in range(size):
            b = Bitvector[size](True for i in range(size))
            b[i] = False
            assert bool(b[i]) == False, "unset %d / %d" % (i, size)


def test_bitvector_iter():
    rng = Random(123)
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        # get a somewhat random bitvector
        bools = list(rng.randint(0, 1) == 1 for i in range(size))
        b = Bitvector[size](*bools)
        # Test iterator
        for i, bit in enumerate(b):
            assert bool(bit) == bools[i]


def test_bitlist():
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        for i in range(size):
            b = Bitlist[size](False for i in range(size))
            b[i] = True
            assert bool(b[i]) == True, "set %d / %d" % (i, size)

        for i in range(size):
            b = Bitlist[size](True for i in range(size))
            b[i] = False
            assert bool(b[i]) == False, "unset %d / %d" % (i, size)


def test_bitlist_iter():
    rng = Random(123)
    for limit in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]:
        for length in [0, 1, limit // 2, limit]:
            # get a somewhat random bitvector
            bools = list(rng.randint(0, 1) == 1 for i in range(length))
            b = Bitlist[limit](*bools)
            # Test iterator
            for i, bit in enumerate(b):
                assert bool(bit) == bools[i]
