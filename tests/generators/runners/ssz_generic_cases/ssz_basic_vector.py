from random import Random

from eth2spec.debug.random_value import get_random_ssz_object, RandomizationMode
from eth2spec.utils.ssz.ssz_impl import serialize
from eth2spec.utils.ssz.ssz_typing import (
    BasicView,
    boolean,
    uint8,
    uint16,
    uint32,
    uint64,
    uint128,
    uint256,
    Vector,
)

from .ssz_boolean import INVALID_BOOL_CASES
from .ssz_test_case import invalid_test_case, valid_test_case


def basic_vector_case_fn(
    rng: Random, mode: RandomizationMode, elem_type: type[BasicView], length: int
):
    return get_random_ssz_object(
        rng,
        Vector[elem_type, length],
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
        for length in [1, 2, 3, 4, 5, 8, 16, 31, 512, 513]:
            for mode in random_modes:
                yield (
                    f"vec_{name}_{length}_{mode.to_name()}",
                    valid_test_case(
                        lambda rng=rng, mode=mode, typ=typ, length=length: basic_vector_case_fn(
                            rng, mode, typ, length
                        )
                    ),
                )


def invalid_cases():
    # zero length vectors are illegal
    for name, typ in BASIC_TYPES.items():
        yield f"vec_{name}_0", invalid_test_case(lambda: b"")

    rng = Random(1234)
    for name, typ in BASIC_TYPES.items():
        random_modes = [RandomizationMode.mode_zero, RandomizationMode.mode_max]
        if name != "bool":
            random_modes.append(RandomizationMode.mode_random)
        for length in [1, 2, 3, 4, 5, 8, 16, 31, 512, 513]:
            yield f"vec_{name}_{length}_nil", invalid_test_case(lambda: b"")
            for mode in random_modes:
                if name == "bool":
                    for description, data in INVALID_BOOL_CASES:
                        yield (
                            f"vec_{name}_{length}_{mode.to_name()}_{description}",
                            invalid_test_case(
                                lambda rng=rng,
                                mode=mode,
                                typ=typ,
                                length=length,
                                data=data: serialize(basic_vector_case_fn(rng, mode, typ, length))[
                                    :-1
                                ]
                                + data
                            ),
                        )
                if length == 1:
                    # empty bytes, no elements. It may seem valid, but empty fixed-size elements are not valid SSZ.
                    yield (
                        f"vec_{name}_{length}_{mode.to_name()}_one_less",
                        invalid_test_case(lambda: b""),
                    )
                else:
                    yield (
                        f"vec_{name}_{length}_{mode.to_name()}_one_less",
                        invalid_test_case(
                            lambda rng=rng, mode=mode, typ=typ, length=length: serialize(
                                basic_vector_case_fn(rng, mode, typ, length - 1)
                            )
                        ),
                    )
                yield (
                    f"vec_{name}_{length}_{mode.to_name()}_one_more",
                    invalid_test_case(
                        lambda rng=rng, mode=mode, typ=typ, length=length: serialize(
                            basic_vector_case_fn(rng, mode, typ, length + 1)
                        )
                    ),
                )
                yield (
                    f"vec_{name}_{length}_{mode.to_name()}_one_byte_less",
                    invalid_test_case(
                        lambda rng=rng, mode=mode, typ=typ, length=length: serialize(
                            basic_vector_case_fn(rng, mode, typ, length)
                        )[:-1]
                    ),
                )
                yield (
                    f"vec_{name}_{length}_{mode.to_name()}_one_byte_more",
                    invalid_test_case(
                        lambda rng=rng, mode=mode, typ=typ, length=length: serialize(
                            basic_vector_case_fn(rng, mode, typ, length)
                        )
                        + serialize(basic_vector_case_fn(rng, mode, uint8, 1))
                    ),
                )
