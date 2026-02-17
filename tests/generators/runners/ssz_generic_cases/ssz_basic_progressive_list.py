from random import Random

from eth2spec.debug.random_value import get_random_ssz_object, RandomizationMode
from eth2spec.test.exceptions import SkippedTest
from eth2spec.utils.ssz.ssz_impl import serialize
from eth2spec.utils.ssz.ssz_typing import (
    BasicView,
    boolean,
    ProgressiveList,
    uint8,
    uint16,
    uint32,
    uint64,
    uint128,
    uint256,
)

from .ssz_boolean import INVALID_BOOL_CASES
from .ssz_test_case import invalid_test_case, valid_test_case
from .ssz_uints import uint_case_fn


def progressive_list_case_fn(
    rng: Random, mode: RandomizationMode, elem_type: type[BasicView], length: int
):
    return get_random_ssz_object(
        rng,
        ProgressiveList[elem_type],
        max_bytes_length=length * 8,
        max_list_length=length,
        mode=mode,
        chaos=False,
    )


BASIC_TYPES: dict[str, type[BasicView]] = {
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
                yield (
                    f"proglist_{name}_{mode.to_name()}_{length}",
                    valid_test_case(
                        lambda rng, mode=mode, typ=typ, length=length: progressive_list_case_fn(
                            rng, mode, typ, length
                        ),
                        rng,
                    ),
                )


def invalid_cases():
    rng = Random(1234)
    for name, typ in BASIC_TYPES.items():
        random_modes = [RandomizationMode.mode_zero, RandomizationMode.mode_max]
        if name != "bool":
            random_modes.append(RandomizationMode.mode_random)
        for length in [0, 1, 2, 3, 4, 5, 8, 20, 21, 22, 85, 86, 341, 342, 1365, 1366]:
            for mode in random_modes:
                if name == "bool":
                    for description, data in INVALID_BOOL_CASES:
                        yield (
                            f"proglist_{name}_{length}_{mode.to_name()}_{description}",
                            invalid_test_case(
                                ProgressiveList[typ],
                                lambda rng, mode=mode, typ=typ, length=length, data=data: (
                                    serialize(progressive_list_case_fn(rng, mode, typ, length))[:-1]
                                    + data
                                ),
                                rng,
                            ),
                        )
                if typ.type_byte_length() > 1:
                    if length > 0:

                        def the_test(rng, mode=mode, typ=typ, length=length):
                            serialized = serialize(progressive_list_case_fn(rng, mode, typ, length))
                            if len(serialized) == 0:
                                raise SkippedTest("Cannot invalidate by removing a byte")
                            return serialized[:-1]

                        yield (
                            f"proglist_{name}_{length}_{mode.to_name()}_one_byte_less",
                            invalid_test_case(
                                ProgressiveList[typ],
                                the_test,
                                rng,
                            ),
                        )
                    yield (
                        f"proglist_{name}_{length}_{mode.to_name()}_one_byte_more",
                        invalid_test_case(
                            ProgressiveList[typ],
                            lambda rng, mode=mode, typ=typ, length=length: (
                                serialize(progressive_list_case_fn(rng, mode, typ, length))
                                + serialize(uint_case_fn(rng, mode, uint8))
                            ),
                            rng,
                        ),
                    )
