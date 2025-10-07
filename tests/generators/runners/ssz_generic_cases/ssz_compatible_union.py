from itertools import permutations
from random import Random

from eth2spec.debug.random_value import RandomizationMode
from eth2spec.test.exceptions import SkippedTest
from eth2spec.utils.ssz.ssz_impl import deserialize, serialize
from eth2spec.utils.ssz.ssz_typing import (
    CompatibleUnion,
    View,
)

from .ssz_container import (
    container_case_fn,
)
from .ssz_progressive_container import (
    ProgressiveSingleFieldContainerTestStruct,
    ProgressiveSingleListContainerTestStruct,
    ProgressiveVarTestStruct,
)
from .ssz_test_case import invalid_test_case, valid_test_case

CompatibleUnionA = CompatibleUnion({1: ProgressiveSingleFieldContainerTestStruct})

CompatibleUnionBC = CompatibleUnion(
    {2: ProgressiveSingleListContainerTestStruct, 3: ProgressiveVarTestStruct}
)

CompatibleUnionABCA = CompatibleUnion(
    {
        1: ProgressiveSingleFieldContainerTestStruct,
        2: ProgressiveSingleListContainerTestStruct,
        3: ProgressiveVarTestStruct,
        4: ProgressiveSingleFieldContainerTestStruct,
    }
)

PRESET_COMPATIBLE_UNIONS: dict[str, type[View]] = {
    "CompatibleUnionA": CompatibleUnionA,
    "CompatibleUnionBC": CompatibleUnionBC,
    "CompatibleUnionABCA": CompatibleUnionABCA,
}


def valid_compatible_union_cases(rng: Random, name: str, typ: type[View]):
    for option, elem_type in typ.options().items():
        for mode in [RandomizationMode.mode_zero, RandomizationMode.mode_max]:
            yield (
                f"{name}_{mode.to_name()}_selector_{option}",
                valid_test_case(
                    lambda rng=rng,
                    mode=mode,
                    typ=typ,
                    elem_type=elem_type,
                    option=option: deserialize(
                        typ,
                        bytes([option]) + serialize(container_case_fn(rng, mode, elem_type)),
                    )
                ),
            )
        for mode in list(RandomizationMode):
            for variation in range(3):
                yield (
                    f"{name}_{mode.to_name()}_selector_{option}_chaos_{variation}",
                    valid_test_case(
                        lambda rng=rng,
                        mode=mode,
                        typ=typ,
                        elem_type=elem_type,
                        option=option: deserialize(
                            typ,
                            bytes([option])
                            + serialize(container_case_fn(rng, mode, elem_type, chaos=True)),
                        )
                    ),
                )
            if mode == RandomizationMode.mode_random:
                for variation in range(10):
                    yield (
                        f"{name}_{mode.to_name()}_selector_{option}_{variation}",
                        valid_test_case(
                            lambda rng=rng,
                            mode=mode,
                            typ=typ,
                            elem_type=elem_type,
                            option=option: deserialize(
                                typ,
                                bytes([option])
                                + serialize(container_case_fn(rng, mode, elem_type)),
                            )
                        ),
                    )


def valid_cases():
    rng = Random(1234)
    for name, typ in PRESET_COMPATIBLE_UNIONS.items():
        yield from valid_compatible_union_cases(rng, name, typ)


def invalid_cases():
    rng = Random(1234)
    for name, typ in PRESET_COMPATIBLE_UNIONS.items():
        options = typ.options()

        # No selector and no data. Always invalid
        yield (
            f"{name}_empty",
            invalid_test_case(typ, lambda: b""),
        )

        # Only selector without any data. Always invalid
        for option in range(0, 255):
            yield (
                f"{name}_selector_{option}_none",
                invalid_test_case(typ, lambda option=option: bytes([option])),
            )

        for mode in list(RandomizationMode):
            # Valid selector but with data from different type option. Not guaranteed to invalidate if data accidentally compatible
            for option_a, option_b in permutations(options, 2):
                elem_type_b = options[option_b]

                def the_test(
                    rng=rng, mode=mode, typ=typ, elem_type_b=elem_type_b, option_a=option_a
                ):
                    serialized = bytes([option_a]) + serialize(
                        container_case_fn(rng, mode, elem_type_b)
                    )
                    try:
                        _ = deserialize(typ, serialized)
                    except Exception:
                        return serialized
                    raise SkippedTest(
                        "The serialized data still parses fine, it's not invalid data"
                    )

                yield (
                    f"{name}_{mode.to_name()}_selector_{option_a}_with_{option_b}_data",
                    invalid_test_case(typ, the_test),
                )

            # Unsupported type option. Always invalid
            for option in range(0, 255):
                if option not in options:

                    def the_test(rng=rng, mode=mode, typ=typ, option=option):
                        serialized = serialize(container_case_fn(rng, mode, typ))
                        serialized = bytes([option]) + serialized[1:]
                        return serialized

                    yield (
                        f"{name}_{mode.to_name()}_selector_{option}_invalid",
                        invalid_test_case(typ, the_test),
                    )

            # Extra byte between selector and data. Not guaranteed to invalidate for variable length data types
            def the_test(
                rng=rng,
                mode=mode,
                typ=typ,
            ):
                serialized = serialize(container_case_fn(rng, mode, typ))
                serialized = bytes([serialized[0]]) + b"\x00" + serialized[1:]
                try:
                    _ = deserialize(typ, serialized)
                except Exception:
                    return serialized
                raise SkippedTest("The serialized data still parses fine, it's not invalid data")

            yield (
                f"{name}_{mode.to_name()}_extra_padding",
                invalid_test_case(typ, the_test),
            )

            # Raw data, without selector. Not guaranteed to invalidate if first byte randomly is a valid selector
            def the_test(
                rng=rng,
                mode=mode,
                typ=typ,
            ):
                serialized = serialize(container_case_fn(rng, mode, typ))
                serialized = serialized[1:]
                try:
                    _ = deserialize(typ, serialized)
                except Exception:
                    return serialized
                raise SkippedTest("The serialized data still parses fine, it's not invalid data")

            yield (
                f"{name}_{mode.to_name()}_selector_missing",
                invalid_test_case(typ, the_test),
            )

            # Extra byte at end. Not guaranteed to invalidate for variable length data types
            def the_test(
                rng=rng,
                mode=mode,
                typ=typ,
            ):
                serialized = serialize(container_case_fn(rng, mode, typ))
                serialized = serialized + b"\x00"
                try:
                    _ = deserialize(typ, serialized)
                except Exception:
                    return serialized
                raise SkippedTest("The serialized data still parses fine, it's not invalid data")

            yield (
                f"{name}_{mode.to_name()}_extra_byte",
                invalid_test_case(typ, the_test),
            )
