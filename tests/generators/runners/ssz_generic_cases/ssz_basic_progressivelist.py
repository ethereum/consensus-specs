from .ssz_test_case import valid_test_case
from eth2spec.utils.ssz.ssz_typing import (
    boolean,
    uint8,
    uint16,
    uint32,
    uint64,
    uint128,
    uint256,
    ProgressiveList,
    BasicView,
)
from random import Random
from typing import Dict, Type
from eth2spec.debug.random_value import RandomizationMode, get_random_ssz_object


def progressive_list_case_fn(
    rng: Random, mode: RandomizationMode, elem_type: Type[BasicView], length: int
):
    return get_random_ssz_object(
        rng,
        ProgressiveList[elem_type],
        max_bytes_length=length * 8,
        max_list_length=length,
        mode=mode,
        chaos=False,
    )


BASIC_TYPES: Dict[str, Type[BasicView]] = {
    "bool": boolean,
    "uint8": uint8,
    "uint16": uint16,
    "uint32": uint32,
    "uint64": uint64,
    "uint128": uint128,
    "uint256": uint256,
}


def valid_cases():
    rng = Random(1234)
    for name, typ in BASIC_TYPES.items():
        random_modes = [RandomizationMode.mode_zero, RandomizationMode.mode_max]
        if name != "bool":
            random_modes.append(RandomizationMode.mode_random)
        for length in [0, 1, 2, 3, 4, 5, 8, 20, 21, 22, 85, 86, 341, 342, 1365, 1366]:
            for mode in random_modes:
                yield f"proglist_{name}_{mode.to_name()}_{length}", valid_test_case(
                    lambda rng=rng, mode=mode, typ=typ, length=length: progressive_list_case_fn(
                        rng, mode, typ, length
                    )
                )


def invalid_cases():
    yield from []  # Consistently enable `yield from` syntax in calling tests
