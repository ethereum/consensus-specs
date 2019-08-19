from typing import Iterable
from eth2spec.utils.ssz.ssz_impl import serialize, hash_tree_root
from eth2spec.utils.ssz.ssz_typing import (
    bit, boolean, Container, List, Vector, ByteList, ByteVector,
    Bitlist, Bitvector,
    uint8, uint16, uint32, uint64, uint256, byte
)
from eth2spec.utils.hash_function import hash as bytes_hash

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
    D: ByteList[256]
    E: VarTestStruct
    F: Vector[FixedTestStruct, 4]
    G: Vector[VarTestStruct, 2]


sig_test_data = [0 for i in range(96)]
for k, v in {0: 1, 32: 2, 64: 3, 95: 0xff}.items():
    sig_test_data[k] = v


def chunk(hex: str) -> str:
    return (hex + ("00" * 32))[:64]  # just pad on the right, to 32 bytes (64 hex chars)


def h(a: str, b: str) -> str:
    return bytes_hash(bytes.fromhex(a) + bytes.fromhex(b)).hex()


# zero hashes, as strings, for
zero_hashes = [chunk("")]
for layer in range(1, 32):
    zero_hashes.append(h(zero_hashes[layer - 1], zero_hashes[layer - 1]))


def merge(a: str, branch: Iterable[str]) -> str:
    """
    Merge (out on left, branch on right) leaf a with branch items, branch is from bottom to top.
    """
    out = a
    for b in branch:
        out = h(out, b)
    return out


test_data = [
    ("bit F", bit(False), "00", chunk("00")),
    ("bit T", bit(True), "01", chunk("01")),
    ("boolean F", boolean(False), "00", chunk("00")),
    ("boolean T", boolean(True), "01", chunk("01")),
    ("bitvector TTFTFTFF", Bitvector[8](1, 1, 0, 1, 0, 1, 0, 0), "2b", chunk("2b")),
    ("bitlist TTFTFTFF", Bitlist[8](1, 1, 0, 1, 0, 1, 0, 0), "2b01", h(chunk("2b"), chunk("08"))),
    ("bitvector FTFT", Bitvector[4](0, 1, 0, 1), "0a", chunk("0a")),
    ("bitlist FTFT", Bitlist[4](0, 1, 0, 1), "1a", h(chunk("0a"), chunk("04"))),
    ("bitvector FTF", Bitvector[3](0, 1, 0), "02", chunk("02")),
    ("bitlist FTF", Bitlist[3](0, 1, 0), "0a", h(chunk("02"), chunk("03"))),
    ("bitvector TFTFFFTTFT", Bitvector[10](1, 0, 1, 0, 0, 0, 1, 1, 0, 1), "c502", chunk("c502")),
    ("bitlist TFTFFFTTFT", Bitlist[16](1, 0, 1, 0, 0, 0, 1, 1, 0, 1), "c506", h(chunk("c502"), chunk("0A"))),
    ("bitvector TFTFFFTTFTFFFFTT", Bitvector[16](1, 0, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1),
     "c5c2", chunk("c5c2")),
    ("bitlist TFTFFFTTFTFFFFTT", Bitlist[16](1, 0, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1),
     "c5c201", h(chunk("c5c2"), chunk("10"))),
    ("long bitvector", Bitvector[512](1 for i in range(512)),
     "ff" * 64, h("ff" * 32, "ff" * 32)),
    ("long bitlist", Bitlist[512](1),
     "03", h(h(chunk("01"), chunk("")), chunk("01"))),
    ("long bitlist", Bitlist[512](1 for i in range(512)),
     "ff" * 64 + "01", h(h("ff" * 32, "ff" * 32), chunk("0002"))),
    ("odd bitvector", Bitvector[513](1 for i in range(513)),
     "ff" * 64 + "01", h(h("ff" * 32, "ff" * 32), h(chunk("01"), chunk("")))),
    ("odd bitlist", Bitlist[513](1 for i in range(513)),
     "ff" * 64 + "03", h(h(h("ff" * 32, "ff" * 32), h(chunk("01"), chunk(""))), chunk("0102"))),
    ("uint8 00", uint8(0x00), "00", chunk("00")),
    ("uint8 01", uint8(0x01), "01", chunk("01")),
    ("uint8 ab", uint8(0xab), "ab", chunk("ab")),
    ("byte 00", byte(0x00), "00", chunk("00")),
    ("byte 01", byte(0x01), "01", chunk("01")),
    ("byte ab", byte(0xab), "ab", chunk("ab")),
    ("uint16 0000", uint16(0x0000), "0000", chunk("0000")),
    ("uint16 abcd", uint16(0xabcd), "cdab", chunk("cdab")),
    ("uint32 00000000", uint32(0x00000000), "00000000", chunk("00000000")),
    ("uint32 01234567", uint32(0x01234567), "67452301", chunk("67452301")),
    ("small (4567, 0123)", SmallTestStruct(A=0x4567, B=0x0123), "67452301", h(chunk("6745"), chunk("2301"))),
    ("small [4567, 0123]::2", Vector[uint16, 2](uint16(0x4567), uint16(0x0123)), "67452301", chunk("67452301")),
    ("uint32 01234567", uint32(0x01234567), "67452301", chunk("67452301")),
    ("uint64 0000000000000000", uint64(0x00000000), "0000000000000000", chunk("0000000000000000")),
    ("uint64 0123456789abcdef", uint64(0x0123456789abcdef), "efcdab8967452301", chunk("efcdab8967452301")),
    ("sig", ByteVector[96](*sig_test_data),
     "0100000000000000000000000000000000000000000000000000000000000000"
     "0200000000000000000000000000000000000000000000000000000000000000"
     "03000000000000000000000000000000000000000000000000000000000000ff",
     h(h(chunk("01"), chunk("02")),
       h("03000000000000000000000000000000000000000000000000000000000000ff", chunk("")))),
    ("emptyTestStruct", EmptyTestStruct(), "", chunk("")),
    ("singleFieldTestStruct", SingleFieldTestStruct(A=0xab), "ab", chunk("ab")),
    ("uint16 list", List[uint16, 32](uint16(0xaabb), uint16(0xc0ad), uint16(0xeeff)), "bbaaadc0ffee",
     h(h(chunk("bbaaadc0ffee"), chunk("")), chunk("03000000"))  # max length: 32 * 2 = 64 bytes = 2 chunks
     ),
    ("uint32 list", List[uint32, 128](uint32(0xaabb), uint32(0xc0ad), uint32(0xeeff)), "bbaa0000adc00000ffee0000",
     # max length: 128 * 4 = 512 bytes = 16 chunks
     h(merge(chunk("bbaa0000adc00000ffee0000"), zero_hashes[0:4]), chunk("03000000"))
     ),
    ("uint256 list", List[uint256, 32](uint256(0xaabb), uint256(0xc0ad), uint256(0xeeff)),
     "bbaa000000000000000000000000000000000000000000000000000000000000"
     "adc0000000000000000000000000000000000000000000000000000000000000"
     "ffee000000000000000000000000000000000000000000000000000000000000",
     h(merge(h(h(chunk("bbaa"), chunk("adc0")), h(chunk("ffee"), chunk(""))), zero_hashes[2:5]), chunk("03000000"))
     ),
    ("uint256 list long", List[uint256, 128](i for i in range(1, 20)),
     "".join([i.to_bytes(length=32, byteorder='little').hex() for i in range(1, 20)]),
     h(merge(
         h(
             h(
                 h(
                     h(h(chunk("01"), chunk("02")), h(chunk("03"), chunk("04"))),
                     h(h(chunk("05"), chunk("06")), h(chunk("07"), chunk("08"))),
                 ),
                 h(
                     h(h(chunk("09"), chunk("0a")), h(chunk("0b"), chunk("0c"))),
                     h(h(chunk("0d"), chunk("0e")), h(chunk("0f"), chunk("10"))),
                 )
             ),
             h(
                 h(
                     h(h(chunk("11"), chunk("12")), h(chunk("13"), chunk(""))),
                     zero_hashes[2]
                 ),
                 zero_hashes[3]
             )
         ),
         zero_hashes[5:7]), chunk("13000000"))  # 128 chunks = 7 deep
     ),
    ("fixedTestStruct", FixedTestStruct(A=0xab, B=0xaabbccdd00112233, C=0x12345678), "ab33221100ddccbbaa78563412",
     h(h(chunk("ab"), chunk("33221100ddccbbaa")), h(chunk("78563412"), chunk("")))),
    ("varTestStruct nil", VarTestStruct(A=0xabcd, C=0xff), "cdab07000000ff",
     h(h(chunk("cdab"), h(zero_hashes[6], chunk("00000000"))), h(chunk("ff"), chunk("")))),
    ("varTestStruct empty", VarTestStruct(A=0xabcd, B=List[uint16, 1024](), C=0xff), "cdab07000000ff",
     h(h(chunk("cdab"), h(zero_hashes[6], chunk("00000000"))), h(chunk("ff"), chunk("")))),  # log2(1024*2/32)= 6 deep
    ("varTestStruct some", VarTestStruct(A=0xabcd, B=List[uint16, 1024](1, 2, 3), C=0xff),
     "cdab07000000ff010002000300",
     h(
         h(
             chunk("cdab"),
             h(
                 merge(
                     chunk("010002000300"),
                     zero_hashes[0:6]
                 ),
                 chunk("03000000")  # length mix in
             )
         ),
         h(chunk("ff"), chunk(""))
    )),
    ("complexTestStruct",
     ComplexTestStruct(
         A=0xaabb,
         B=List[uint16, 128](0x1122, 0x3344),
         C=0xff,
         D=ByteList[256](b"foobar"),
         E=VarTestStruct(A=0xabcd, B=List[uint16, 1024](1, 2, 3), C=0xff),
         F=Vector[FixedTestStruct, 4](
             FixedTestStruct(A=0xcc, B=0x4242424242424242, C=0x13371337),
             FixedTestStruct(A=0xdd, B=0x3333333333333333, C=0xabcdabcd),
             FixedTestStruct(A=0xee, B=0x4444444444444444, C=0x00112233),
             FixedTestStruct(A=0xff, B=0x5555555555555555, C=0x44556677)),
         G=Vector[VarTestStruct, 2](
             VarTestStruct(A=0xdead, B=List[uint16, 1024](1, 2, 3), C=0x11),
             VarTestStruct(A=0xbeef, B=List[uint16, 1024](4, 5, 6), C=0x22)),
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
     "adde0700000011010002000300"
     "efbe0700000022040005000600",
     h(
         h(
             h(  # A and B
                 chunk("bbaa"),
                 h(merge(chunk("22114433"), zero_hashes[0:3]), chunk("02000000"))  # 2*128/32 = 8 chunks
             ),
             h(  # C and D
                 chunk("ff"),
                 h(merge(chunk("666f6f626172"), zero_hashes[0:3]), chunk("06000000"))  # 256/32 = 8 chunks
             )
         ),
         h(
             h(  # E and F
                 h(h(chunk("cdab"), h(merge(chunk("010002000300"), zero_hashes[0:6]), chunk("03000000"))),
                   h(chunk("ff"), chunk(""))),
                 h(
                     h(
                         h(h(chunk("cc"), chunk("4242424242424242")), h(chunk("37133713"), chunk(""))),
                         h(h(chunk("dd"), chunk("3333333333333333")), h(chunk("cdabcdab"), chunk(""))),
                     ),
                     h(
                         h(h(chunk("ee"), chunk("4444444444444444")), h(chunk("33221100"), chunk(""))),
                         h(h(chunk("ff"), chunk("5555555555555555")), h(chunk("77665544"), chunk(""))),
                     ),
                 )
             ),
             h(  # G and padding
                 h(
                     h(h(chunk("adde"), h(merge(chunk("010002000300"), zero_hashes[0:6]), chunk("03000000"))),
                       h(chunk("11"), chunk(""))),
                     h(h(chunk("efbe"), h(merge(chunk("040005000600"), zero_hashes[0:6]), chunk("03000000"))),
                       h(chunk("22"), chunk(""))),
                 ),
                 chunk("")
             )
         )
     ))
]


@pytest.mark.parametrize("name, value, serialized, _", test_data)
def test_serialize(name, value, serialized, _):
    assert serialize(value) == bytes.fromhex(serialized)


@pytest.mark.parametrize("name, value, _, root", test_data)
def test_hash_tree_root(name, value, _, root):
    assert hash_tree_root(value) == bytes.fromhex(root)
