# flake8: noqa
# Ignore linter: This module makes importing SSZ types easy, and hides away the underlying library from the spec.

from remerkleable.complex import Container, Vector, List
from remerkleable.union import Union
from remerkleable.basic import (
    boolean,
    bit,
    uint,
    byte,
    uint8,
    uint16,
    uint32,
    uint64,
    uint128,
    uint256,
)
from remerkleable.bitfields import Bitvector, Bitlist
from remerkleable.byte_arrays import (
    ByteVector,
    Bytes1,
    Bytes4,
    Bytes8,
    Bytes32,
    Bytes48,
    Bytes96,
    ByteList,
)
from remerkleable.core import BasicView, View, Path


Bytes20 = ByteVector[20]  # type: ignore
Bytes31 = ByteVector[31]  # type: ignore
