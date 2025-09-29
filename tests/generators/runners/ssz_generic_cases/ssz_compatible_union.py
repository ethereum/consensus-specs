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
                f"{name}_{mode.to_name()}",
                valid_test_case(
                    lambda rng=rng, mode=mode, elem_type=elem_type, option=option: (
                        bytes([option]) + container_case_fn(rng, mode, elem_type)
                    )
                ),
            )
        for mode in list(RandomizationMode):
            for variation in range(3):
                yield (
                    f"{name}_{mode.to_name()}_chaos_{variation}",
                    valid_test_case(
                        lambda rng=rng, mode=mode, elem_type=elem_type, option=option: (
                            bytes([option]) + container_case_fn(rng, mode, elem_type, chaos=True)
                        )
                    ),
                )
            if mode == RandomizationMode.mode_random:
                for variation in range(10):
                    yield (
                        f"{name}_{mode.to_name()}_{variation}",
                        valid_test_case(
                            valid_test_case(
                                lambda rng=rng, mode=mode, elem_type=elem_type, option=option: (
                                    bytes([option]) + container_case_fn(rng, mode, elem_type)
                                )
                            ),
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
        yield (
            f"{name}_empty",
            invalid_test_case(typ, lambda: b""),
        )
        for option in range(0, 255):
            yield (
                f"{name}_selector_{option}_none",
                invalid_test_case(typ, lambda option=option: bytes([option])),
            )
        for mode in list(RandomizationMode):
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
