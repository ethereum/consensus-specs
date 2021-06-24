# Imports
from lru import LRU
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any, Callable, Dict, Set, Sequence, Tuple, Optional, TypeVar, NamedTuple
)

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist)
from eth2spec.utils.ssz.ssz_typing import Bitvector  # noqa: F401
from eth2spec.utils import bls
from eth2spec.utils.hash_function import hash

# Preparations
SSZObject = TypeVar('SSZObject', bound=View)


def ceillog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return uint64((x - 1).bit_length())


def floorlog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"floorlog2 accepts only positive values, x={x}")
    return uint64(x.bit_length() - 1)
