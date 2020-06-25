from typing import Type, List, Callable

import pytest

from remerkleable.basic import uint, uint8, uint16, uint32, uint64, uint128, uint256, \
    OperationNotSupported

uint_types = [uint8, uint16, uint32, uint64, uint128, uint256]

uint_valid_cases: List[Callable[[Type[uint]], int]] = [
    lambda t: 0,
    lambda t: 1,
    lambda t: 3,
    lambda t: 53,
    lambda t: (1 << (8 * t.type_byte_length())) // 10,
    lambda t: (1 << (8 * t.type_byte_length())) // 2,
    lambda t: (1 << (8 * t.type_byte_length()))-1,
]

bi_operations = ['add', 'sub', 'floordiv', 'mul', 'mod', 'and', 'xor', 'or']
reverse_bi_operations = [f'r{op}' for op in bi_operations]


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
@pytest.mark.parametrize("b", uint_valid_cases)
@pytest.mark.parametrize("op", bi_operations + reverse_bi_operations)
@pytest.mark.parametrize("b_unsigned", [True, False])
def test_uint_arithmetic(typ, a, b, op, b_unsigned):
    a_v = a(typ)
    b_v = b(typ)
    uint_a = typ(a_v)
    uint_b = typ(b_v)
    f = getattr(a_v, f'__{op}__')
    regular_err = None
    int_v = -1
    try:
        int_v = f(b_v)
    except Exception as e:
        regular_err = e

    err = None
    uint_v = None
    try:
        uint_f = getattr(uint_a, f'__{op}__')
        uint_v = uint_f(uint_b if b_unsigned else b_v)
    except Exception as e:
        err = e

    # E.g. divide by zero, modulo errors, etc. If it doesn't work for a python int, it shouldn't work for a uint as well
    if err is not None and (err == regular_err or isinstance(err, type(regular_err))):
        return

    if int_v < 0 or int_v >= (1 << (8 * typ.type_byte_length())):
        assert isinstance(err, ValueError)
    else:
        assert int(uint_v) == int_v
        assert uint_v == typ(int_v)
        assert isinstance(uint_v, typ)


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("v", [-256, -255, -3, -1])
def test_uint_lower_bound(typ, v):
    try:
        typ(v)
        raise Exception('expected value error')
    except ValueError:
        pass


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("vf", [
    lambda t: (1 << (8 * t.type_byte_length())),
    lambda t: (1 << (8 * t.type_byte_length())) + 1,
    lambda t: (1 << (16 * t.type_byte_length())),
])
def test_uint_upper_bound(typ, vf):
    try:
        int_v = vf(typ)
        typ(int_v)
        raise Exception('expected value error')
    except ValueError:
        pass


shift_cases: List[Callable[[Type[uint]], int]] = [
    lambda t: 0,
    lambda t: 1,
    lambda t: 2,
    lambda t: 8,
    lambda t: (8 * t.type_byte_length()) // 10,
    lambda t: (8 * t.type_byte_length()) // 2,
    lambda t: (8 * t.type_byte_length()) - 1,
    lambda t: (8 * t.type_byte_length()),
    lambda t: (8 * t.type_byte_length()) + 1,
    lambda t: (8 * t.type_byte_length()) * 2,
]

shift_operations = ['lshift', 'rshift']


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
@pytest.mark.parametrize("b", shift_cases)
@pytest.mark.parametrize("op", shift_operations)
@pytest.mark.parametrize("b_unsigned", [True, False])
def test_uint_shifts(typ, a, b, op, b_unsigned):
    a_v = a(typ)
    b_v = b(typ)
    uint_a = typ(a_v)
    uint_b = typ(b_v)
    f = getattr(a_v, f'__{op}__')
    int_v = f(b_v)
    uint_f = getattr(uint_a, f'__{op}__')
    uint_v = uint_f(uint_b if b_unsigned else b_v)
    mask = (1 << (typ.type_byte_length() << 3)) - 1
    assert mask.to_bytes(length=typ.type_byte_length(), byteorder='little').hex() == 'ff' * typ.type_byte_length()
    assert (int_v & mask) == int(uint_v)


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
@pytest.mark.parametrize("b_v", [0, 1, 2, 3, 5])
@pytest.mark.parametrize("rev", [True, False])
@pytest.mark.parametrize("b_unsigned", [True, False])
def test_uint_pow(typ, a, b_v, rev, b_unsigned):
    a_v = a(typ)
    uint_a = typ(a_v)
    uint_b = typ(b_v)

    regular_err = None
    int_v = -1
    try:
        int_v = a_v**b_v
    except Exception as e:
        regular_err = e

    err = None
    uint_v = None
    try:
        uint_v = uint_a**(uint_b if b_unsigned else b_v)
    except Exception as e:
        err = e

    # If python ints can't handle it either, then it's ok
    if err is not None and (err == regular_err or isinstance(err, type(regular_err))):
        return

    if int_v < 0 or int_v >= (1 << (8 * typ.type_byte_length())):
        assert isinstance(err, ValueError)
    else:
        assert int(uint_v) == int_v
        assert uint_v == typ(int_v)
        assert isinstance(uint_v, typ)


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
def test_uint_negative(typ, a):
    a_v = a(typ)
    uint_a = typ(a_v)
    try:
        x = -uint_a
        raise Exception(f"expected OperationNotSupported exception, but got result {x}")
    except OperationNotSupported:
        pass


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
@pytest.mark.parametrize("op", ['truediv', 'rtruediv', 'rlshift', 'rrshift'])
def test_uint_bi_op_unsupported(typ, a, op):
    a_v = a(typ)
    uint_a = typ(a_v)
    uint_f = getattr(uint_a, f'__{op}__')
    try:
        x = uint_f(42)
        raise Exception(f"expected OperationNotSupported exception, but got result {x}")
    except OperationNotSupported:
        pass


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
def test_uint_identity(typ, a):
    a_v = a(typ)
    uint_a = typ(a_v)
    assert a_v == abs(uint_a)
    assert a_v == +uint_a


@pytest.mark.parametrize("typ", uint_types)
@pytest.mark.parametrize("a", uint_valid_cases)
def test_uint_invert(typ, a):
    a_v = a(typ)
    uint_a = typ(a_v)
    inverted_a = ~uint_a
    mask = (1 << (typ.type_byte_length() << 3)) - 1
    assert uint_a | inverted_a == mask
    assert inverted_a != uint_a
    bitlen = uint_a.type_byte_length() * 8
    bits = [(1 << i) & uint_a != 0 for i in range(bitlen)]
    inverted_bits = [(1 << i) & inverted_a != 0 for i in range(bitlen)]
    assert all(bits[i] != inverted_bits[i] for i in range(bitlen))
