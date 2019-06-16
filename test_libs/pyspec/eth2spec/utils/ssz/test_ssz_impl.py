from .ssz_impl import serialize, serialize_basic, encode_series, signing_root, hash_tree_root
from .ssz_typing import (
    SSZValue, SSZType, BasicValue, BasicType, Series, ElementsType, Bit, Container, List, Vector, Bytes, BytesN,
    uint, uint8, uint16, uint32, uint64, uint128, uint256, byte
)

import pytest


class EmptyTestStruct(Container):
    pass


class SingleFieldTestStruct(Container):
    A: byte


class SmallTestStruct(Container):
    A: uint16
    B: uint16


class FixedTestStruct(Container):
    A: uint8
    B: uint64
    C: uint32


class VarTestStruct(Container):
    A: uint16
    B: List[uint16, 1024]
    C: uint8


class ComplexTestStruct(Container):
    A: uint16
    B: List[uint16, 128]
    C: uint8
    D: Bytes[256]
    E: VarTestStruct
    F: Vector[FixedTestStruct, 4]
    G: Vector[VarTestStruct, 2]


sig_test_data = [0 for i in range(96)]
for k, v in {0: 1, 32: 2, 64: 3, 95: 0xff}.items():
    sig_test_data[k] = v

test_data = [
    ("bool F", Bit(False), "00"),
    ("bool T", Bit(True), "01"),
    ("uint8 00", uint8(0x00), "00"),
    ("uint8 01", uint8(0x01), "01"),
    ("uint8 ab", uint8(0xab), "ab"),
    ("uint16 0000", uint16(0x0000), "0000"),
    ("uint16 abcd", uint16(0xabcd), "cdab"),
    ("uint32 00000000", uint32(0x00000000), "00000000"),
    ("uint32 01234567", uint32(0x01234567), "67452301"),
    ("small (4567, 0123)", SmallTestStruct(A=0x4567, B=0x0123), "67452301"),
    ("small [4567, 0123]::2", Vector[uint16, 2](uint16(0x4567), uint16(0x0123)), "67452301"),
    ("uint32 01234567", uint32(0x01234567), "67452301"),
    ("uint64 0000000000000000", uint64(0x00000000), "0000000000000000"),
    ("uint64 0123456789abcdef", uint64(0x0123456789abcdef), "efcdab8967452301"),
    ("sig", BytesN[96](*sig_test_data),
     "0100000000000000000000000000000000000000000000000000000000000000"
     "0200000000000000000000000000000000000000000000000000000000000000"
     "03000000000000000000000000000000000000000000000000000000000000ff"),
    ("emptyTestStruct", EmptyTestStruct(), ""),
    ("singleFieldTestStruct", SingleFieldTestStruct(A=0xab), "ab"),
    ("fixedTestStruct", FixedTestStruct(A=0xab, B=0xaabbccdd00112233, C=0x12345678), "ab33221100ddccbbaa78563412"),
    ("varTestStruct nil", VarTestStruct(A=0xabcd, C=0xff), "cdab07000000ff"),
    ("varTestStruct empty", VarTestStruct(A=0xabcd, B=List[uint16, 1024](), C=0xff), "cdab07000000ff"),
    ("varTestStruct some", VarTestStruct(A=0xabcd, B=List[uint16, 1024](1, 2, 3), C=0xff),
     "cdab07000000ff010002000300"),
    ("complexTestStruct",
     ComplexTestStruct(
         A=0xaabb,
         B=List[uint16, 128](0x1122, 0x3344),
         C=0xff,
         D=Bytes[256](b"foobar"),
         E=VarTestStruct(A=0xabcd, B=List[uint16, 1024](1, 2, 3), C=0xff),
         F=Vector[FixedTestStruct, 4](
             FixedTestStruct(A=0xcc, B=0x4242424242424242, C=0x13371337),
             FixedTestStruct(A=0xdd, B=0x3333333333333333, C=0xabcdabcd),
             FixedTestStruct(A=0xee, B=0x4444444444444444, C=0x00112233),
             FixedTestStruct(A=0xff, B=0x5555555555555555, C=0x44556677)),
         G=Vector[VarTestStruct, 2](
             VarTestStruct(A=0xabcd, B=List[uint16, 1024](1, 2, 3), C=0xff),
             VarTestStruct(A=0xabcd, B=List[uint16, 1024](1, 2, 3), C=0xff)),
     ),
     "bbaa"
     "47000000"  # offset of B, []uint16
     "ff"
     "4b000000"  # offset of foobar
     "51000000"  # offset of E
     "cc424242424242424237133713"
     "dd3333333333333333cdabcdab"
     "ee444444444444444433221100"
     "ff555555555555555577665544"
     "5e000000"  # pointer to G
     "22114433"  # contents of B
     "666f6f626172"  # foobar
     "cdab07000000ff010002000300"  # contents of E
     "08000000" "15000000"  # [start G]: local offsets of [2]varTestStruct
     "cdab07000000ff010002000300"
     "cdab07000000ff010002000300",
     )
]


@pytest.mark.parametrize("name, value, serialized", test_data)
def test_serialize(name, value, serialized):
    assert serialize(value) == bytes.fromhex(serialized)


@pytest.mark.parametrize("name, value, _", test_data)
def test_hash_tree_root(name, value, _):
    hash_tree_root(value)
