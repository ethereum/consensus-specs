from collections.abc import Sequence
from random import Random

from eth2spec.utils.ssz.ssz_typing import (
    byte,
    List,
    ProgressiveBitlist,
    ProgressiveContainer,
    ProgressiveList,
    uint16,
    uint64,
    View,
)

from .ssz_container import (
    invalid_container_cases,
    SmallTestStruct,
    valid_container_cases,
    VarTestStruct,
)


class ProgressiveSingleFieldContainerTestStruct(ProgressiveContainer(active_fields=[1])):
    A: byte


class ProgressiveSingleListContainerTestStruct(ProgressiveContainer(active_fields=[0, 0, 0, 0, 1])):
    C: ProgressiveBitlist


class ProgressiveVarTestStruct(ProgressiveContainer(active_fields=[1, 0, 1, 0, 1])):
    A: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist


class ProgressiveComplexTestStruct(
    ProgressiveContainer(
        active_fields=[1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1]
    )
):
    A: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist
    D: ProgressiveList[uint64]
    E: ProgressiveList[SmallTestStruct]
    F: ProgressiveList[ProgressiveList[VarTestStruct]]
    G: List[ProgressiveSingleFieldContainerTestStruct, 10]
    H: ProgressiveList[ProgressiveVarTestStruct]


PRESET_PROGRESSIVE_CONTAINERS: dict[str, tuple[type[View], Sequence[int]]] = {
    "ProgressiveSingleFieldContainerTestStruct": (ProgressiveSingleFieldContainerTestStruct, []),
    "ProgressiveSingleListContainerTestStruct": (ProgressiveSingleListContainerTestStruct, [0]),
    "ProgressiveVarTestStruct": (ProgressiveVarTestStruct, [1, 5]),
    "ProgressiveComplexTestStruct": (ProgressiveComplexTestStruct, [1, 5, 9, 13, 17, 21, 25]),
}


def valid_cases():
    rng = Random(1234)
    for name, (typ, offsets) in PRESET_PROGRESSIVE_CONTAINERS.items():
        yield from valid_container_cases(rng, name, typ, offsets)


def invalid_cases():
    rng = Random(1234)
    for name, (typ, offsets) in PRESET_PROGRESSIVE_CONTAINERS.items():
        yield from invalid_container_cases(rng, name, typ, offsets)
