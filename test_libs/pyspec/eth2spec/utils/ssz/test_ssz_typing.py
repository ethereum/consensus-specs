from .ssz_typing import (
    SSZValue, SSZType, BasicValue, BasicType, Series, ElementsType,
    Elements, bit, boolean, Container, List, Vector, Bytes, BytesN,
    byte, uint, uint8, uint16, uint32, uint64, uint128, uint256,
    Bytes32, Bytes48
)


def expect_value_error(fn, msg):
    try:
        fn()
        raise AssertionError(msg)
    except ValueError:
        pass


def test_subclasses():
    for u in [uint, uint8, uint16, uint32, uint64, uint128, uint256]:
        assert issubclass(u, uint)
        assert issubclass(u, int)
        assert issubclass(u, BasicValue)
        assert issubclass(u, SSZValue)
        assert isinstance(u, SSZType)
        assert isinstance(u, BasicType)
    assert issubclass(boolean, BasicValue)
    assert isinstance(boolean, BasicType)

    for c in [Container, List, Vector, Bytes, BytesN]:
        assert issubclass(c, Series)
        assert issubclass(c, SSZValue)
        assert isinstance(c, SSZType)
        assert not issubclass(c, BasicValue)
        assert not isinstance(c, BasicType)

    for c in [List, Vector, Bytes, BytesN]:
        assert issubclass(c, Elements)
        assert isinstance(c, ElementsType)


def test_basic_instances():
    for u in [uint, uint8, byte, uint16, uint32, uint64, uint128, uint256]:
        v = u(123)
        assert isinstance(v, uint)
        assert isinstance(v, int)
        assert isinstance(v, BasicValue)
        assert isinstance(v, SSZValue)

    assert isinstance(boolean(True), BasicValue)
    assert isinstance(boolean(False), BasicValue)
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
        expect_value_error(lambda: k(v), "no overflows allowed")

    for k, _ in max.items():
        # this should work
        assert k(0) == 0
        # but we do not allow underflows
        expect_value_error(lambda: k(-1), "no underflows allowed")


def test_container():
    class Foo(Container):
        a: uint8
        b: uint32

    empty = Foo()
    assert empty.a == uint8(0)
    assert empty.b == uint32(0)

    assert issubclass(Foo, Container)
    assert issubclass(Foo, SSZValue)
    assert issubclass(Foo, Series)

    assert Foo.is_fixed_size()
    x = Foo(a=uint8(123), b=uint32(45))
    assert x.a == 123
    assert x.b == 45
    assert isinstance(x.a, uint8)
    assert isinstance(x.b, uint32)
    assert x.type().is_fixed_size()

    class Bar(Container):
        a: uint8
        b: List[uint8, 1024]

    assert not Bar.is_fixed_size()

    y = Bar(a=123, b=List[uint8, 1024](uint8(1), uint8(2)))
    assert y.a == 123
    assert isinstance(y.a, uint8)
    assert len(y.b) == 2
    assert isinstance(y.a, uint8)
    assert isinstance(y.b, List[uint8, 1024])
    assert not y.type().is_fixed_size()
    assert y.b[0] == 1
    v: List = y.b
    assert v.type().elem_type == uint8
    assert v.type().length == 1024

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


def test_list():
    typ = List[uint64, 128]
    assert issubclass(typ, List)
    assert issubclass(typ, SSZValue)
    assert issubclass(typ, Series)
    assert issubclass(typ, Elements)
    assert isinstance(typ, ElementsType)

    assert not typ.is_fixed_size()

    assert len(typ()) == 0  # empty
    assert len(typ(uint64(0))) == 1  # single arg
    assert len(typ(uint64(i) for i in range(10))) == 10  # generator
    assert len(typ(uint64(0), uint64(1), uint64(2))) == 3  # args
    assert isinstance(typ(1, 2, 3, 4, 5)[4], uint64)  # coercion
    assert isinstance(typ(i for i in range(10))[9], uint64)  # coercion in generator

    v = typ(uint64(0))
    v[0] = uint64(123)
    assert v[0] == 123
    assert isinstance(v[0], uint64)

    assert isinstance(v, List)
    assert isinstance(v, List[uint64, 128])
    assert isinstance(v, typ)
    assert isinstance(v, SSZValue)
    assert isinstance(v, Series)
    assert issubclass(v.type(), Elements)
    assert isinstance(v.type(), ElementsType)

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
    assert isinstance(BytesN[32](b'\xab' * 32), Bytes32)
    assert not isinstance(BytesN[32](b'\xab' * 32), Bytes48)
    assert issubclass(BytesN[32](b'\xab' * 32).type(), Bytes32)
    assert issubclass(BytesN[32], Bytes32)

    class Hash(Bytes32):
        pass

    assert isinstance(Hash(b'\xab' * 32), Bytes32)
    assert not isinstance(Hash(b'\xab' * 32), Bytes48)
    assert issubclass(Hash(b'\xab' * 32).type(), Bytes32)
    assert issubclass(Hash, Bytes32)

    assert not issubclass(Bytes48, Bytes32)

    assert len(Bytes32() + Bytes48()) == 80


def test_uint_math():
    assert uint8(0) + uint8(uint32(16)) == uint8(16)  # allow explicit casting to make invalid addition valid

    expect_value_error(lambda: uint8(0) - uint8(1), "no underflows allowed")
    expect_value_error(lambda: uint8(1) + uint8(255), "no overflows allowed")
    expect_value_error(lambda: uint8(0) + 256, "no overflows allowed")
    expect_value_error(lambda: uint8(42) + uint32(123), "no mixed types")
    expect_value_error(lambda: uint32(42) + uint8(123), "no mixed types")

    assert type(uint32(1234) + 56) == uint32
