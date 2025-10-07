from collections.abc import Sequence
from random import Random

from eth2spec.debug.random_value import RandomizationMode
from eth2spec.test.exceptions import SkippedTest
from eth2spec.utils.ssz.ssz_impl import deserialize, serialize
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
    container_case_fn,
    invalid_container_cases,
    SmallTestStruct,
    valid_container_cases,
    VarTestStruct,
)
from .ssz_test_case import invalid_test_case


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


class ModifiedTestStruct1(ProgressiveContainer(active_fields=[1, 1])):
    A: byte
    X: byte


class ModifiedTestStruct2(ProgressiveContainer(active_fields=[1, 0, 1])):
    A: byte
    B: List[uint16, 123]


class ModifiedTestStruct3(ProgressiveContainer(active_fields=[1, 1, 1])):
    A: byte
    X: byte
    B: List[uint16, 123]


class ModifiedTestStruct4(ProgressiveContainer(active_fields=[0, 0, 1, 0, 1])):
    B: List[uint16, 123]
    C: ProgressiveBitlist


class ModifiedTestStruct5(ProgressiveContainer(active_fields=[1, 0, 0, 0, 1])):
    A: byte
    C: ProgressiveBitlist


class ModifiedTestStruct6(ProgressiveContainer(active_fields=[1, 1, 1, 0, 1, 0, 0, 0, 1])):
    A: byte
    X: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist
    D: ProgressiveList[uint64]


class ModifiedTestStruct7(ProgressiveContainer(active_fields=[1, 0, 1, 0, 0, 0, 0, 0, 1])):
    A: byte
    B: List[uint16, 123]
    D: ProgressiveList[uint64]


class ModifiedTestStruct8(
    ProgressiveContainer(
        active_fields=[1, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1]
    )
):
    A: byte
    X: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist
    D: ProgressiveList[uint64]
    E: ProgressiveList[SmallTestStruct]
    F: ProgressiveList[ProgressiveList[VarTestStruct]]
    G: List[ProgressiveSingleFieldContainerTestStruct, 10]
    H: ProgressiveList[ProgressiveVarTestStruct]


class ModifiedTestStruct9(
    ProgressiveContainer(
        active_fields=[1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1]
    )
):
    A: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist
    D: ProgressiveList[uint64]
    F: ProgressiveList[ProgressiveList[VarTestStruct]]
    G: List[ProgressiveSingleFieldContainerTestStruct, 10]
    H: ProgressiveList[ProgressiveVarTestStruct]


PRESET_PROGRESSIVE_CONTAINERS: dict[str, tuple[type[View], Sequence[int]]] = {
    "ProgressiveSingleFieldContainerTestStruct": (ProgressiveSingleFieldContainerTestStruct, []),
    "ProgressiveSingleListContainerTestStruct": (ProgressiveSingleListContainerTestStruct, [0]),
    "ProgressiveVarTestStruct": (ProgressiveVarTestStruct, [1, 5]),
    "ProgressiveComplexTestStruct": (ProgressiveComplexTestStruct, [1, 5, 9, 13, 17, 21, 25]),
}


MODIFIED_PROGRESSIVE_CONTIANERS: Sequence[type[View]] = {
    ModifiedTestStruct1,
    ModifiedTestStruct2,
    ModifiedTestStruct3,
    ModifiedTestStruct4,
    ModifiedTestStruct5,
    ModifiedTestStruct6,
    ModifiedTestStruct7,
    ModifiedTestStruct8,
    ModifiedTestStruct9,
}


def valid_cases():
    rng = Random(1234)
    for name, (typ, offsets) in PRESET_PROGRESSIVE_CONTAINERS.items():
        yield from valid_container_cases(rng, name, typ, offsets)


def invalid_cases():
    rng = Random(1234)
    for name, (typ, offsets) in PRESET_PROGRESSIVE_CONTAINERS.items():
        yield from invalid_container_cases(rng, name, typ, offsets)

        for mode in [
            RandomizationMode.mode_random,
            RandomizationMode.mode_nil_count,
            RandomizationMode.mode_one_count,
            RandomizationMode.mode_max_count,
        ]:
            for i, modded_typ in enumerate(MODIFIED_PROGRESSIVE_CONTIANERS):

                def the_test(rng, mode=mode, typ=typ, modded_typ=modded_typ):
                    serialized = serialize(container_case_fn(rng, mode, modded_typ))
                    try:
                        _ = deserialize(typ, serialized)
                    except Exception:
                        return serialized
                    raise SkippedTest(
                        "The serialized data still parses fine, it's not invalid data"
                    )

                yield (
                    f"{name}_{mode.to_name()}_modded_{i}",
                    invalid_test_case(typ, the_test, rng),
                )
