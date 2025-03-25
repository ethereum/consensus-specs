from ssz_test_case import invalid_test_case, valid_test_case
from eth2spec.utils.ssz.ssz_typing import (
    View,
    Container,
    byte,
    uint8,
    uint16,
    uint32,
    uint64,
    List,
    ByteList,
    Vector,
    Bitvector,
    Bitlist,
)
from eth2spec.utils.ssz.ssz_impl import serialize
from random import Random
from typing import Dict, Tuple, Sequence, Callable, Type
from eth2spec.debug.random_value import RandomizationMode, get_random_ssz_object


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


class BitsStruct(Container):
    A: Bitlist[5]
    B: Bitvector[2]
    C: Bitvector[1]
    D: Bitlist[6]
    E: Bitvector[8]


def container_case_fn(
    rng: Random, mode: RandomizationMode, typ: Type[View], chaos: bool = False
):
    return get_random_ssz_object(
        rng, typ, max_bytes_length=2000, max_list_length=2000, mode=mode, chaos=chaos
    )


PRESET_CONTAINERS: Dict[str, Tuple[Type[View], Sequence[int]]] = {
    "SingleFieldTestStruct": (SingleFieldTestStruct, []),
    "SmallTestStruct": (SmallTestStruct, []),
    "FixedTestStruct": (FixedTestStruct, []),
    "VarTestStruct": (VarTestStruct, [2]),
    "ComplexTestStruct": (ComplexTestStruct, [2, 2 + 4 + 1, 2 + 4 + 1 + 4]),
    "BitsStruct": (BitsStruct, [0, 4 + 1 + 1, 4 + 1 + 1 + 4]),
}


def valid_cases():
    rng = Random(1234)
    for (name, (typ, offsets)) in PRESET_CONTAINERS.items():
        for mode in [RandomizationMode.mode_zero, RandomizationMode.mode_max]:
            yield f"{name}_{mode.to_name()}", valid_test_case(
                lambda: container_case_fn(rng, mode, typ)
            )

        if len(offsets) == 0:
            modes = [
                RandomizationMode.mode_random,
                RandomizationMode.mode_zero,
                RandomizationMode.mode_max,
            ]
        else:
            modes = list(RandomizationMode)

        for mode in modes:
            for variation in range(3):
                yield f"{name}_{mode.to_name()}_chaos_{variation}", valid_test_case(
                    lambda: container_case_fn(rng, mode, typ, chaos=True)
                )
        # Notes: Below is the second wave of iteration, and only the random mode is selected
        # for container without offset since ``RandomizationMode.mode_zero`` and ``RandomizationMode.mode_max``
        # are deterministic.
        modes = (
            [RandomizationMode.mode_random]
            if len(offsets) == 0
            else list(RandomizationMode)
        )
        for mode in modes:
            for variation in range(10):
                yield f"{name}_{mode.to_name()}_{variation}", valid_test_case(
                    lambda: container_case_fn(rng, mode, typ)
                )


def mod_offset(b: bytes, offset_index: int, change: Callable[[int], int]):
    return (
        b[:offset_index]
        + (
            change(
                int.from_bytes(b[offset_index : offset_index + 4], byteorder="little")
            )
            & 0xFFFFFFFF
        ).to_bytes(length=4, byteorder="little")
        + b[offset_index + 4 :]
    )


def invalid_cases():
    rng = Random(1234)
    for (name, (typ, offsets)) in PRESET_CONTAINERS.items():
        # using mode_max_count, so that the extra byte cannot be picked up as normal list content
        yield f"{name}_extra_byte", invalid_test_case(
            lambda: serialize(
                container_case_fn(rng, RandomizationMode.mode_max_count, typ)
            )
            + b"\xff"
        )

        if len(offsets) != 0:
            # Note: there are many more ways to have invalid offsets,
            # these are just example to get clients started looking into hardening ssz.
            for mode in [
                RandomizationMode.mode_random,
                RandomizationMode.mode_nil_count,
                RandomizationMode.mode_one_count,
                RandomizationMode.mode_max_count,
            ]:
                for index, offset_index in enumerate(offsets):
                    yield f"{name}_{mode.to_name()}_offset_{offset_index}_plus_one", invalid_test_case(
                        lambda: mod_offset(
                            b=serialize(container_case_fn(rng, mode, typ)),
                            offset_index=offset_index,
                            change=lambda x: x + 1,
                        )
                    )
                    yield f"{name}_{mode.to_name()}_offset_{offset_index}_zeroed", invalid_test_case(
                        lambda: mod_offset(
                            b=serialize(container_case_fn(rng, mode, typ)),
                            offset_index=offset_index,
                            change=lambda x: 0,
                        )
                    )
                    if index == 0:
                        yield f"{name}_{mode.to_name()}_offset_{offset_index}_minus_one", invalid_test_case(
                            lambda: mod_offset(
                                b=serialize(container_case_fn(rng, mode, typ)),
                                offset_index=offset_index,
                                change=lambda x: x - 1,
                            )
                        )
                    if mode == RandomizationMode.mode_max_count:
                        serialized = serialize(container_case_fn(rng, mode, typ))
                        serialized = serialized + serialized[:2]
                        yield f"{name}_{mode.to_name()}_last_offset_{offset_index}_overflow", invalid_test_case(
                            lambda: serialized
                        )
                    if mode == RandomizationMode.mode_one_count:
                        serialized = serialize(container_case_fn(rng, mode, typ))
                        serialized = serialized + serialized[:1]
                        yield f"{name}_{mode.to_name()}_last_offset_{offset_index}_wrong_byte_length", invalid_test_case(
                            lambda: serialized
                        )
