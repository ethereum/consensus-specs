from random import Random

from eth2spec.debug.random_value import get_random_ssz_object, RandomizationMode
from eth2spec.utils.ssz.ssz_impl import serialize
from eth2spec.utils.ssz.ssz_typing import Bitlist

from .ssz_test_case import invalid_test_case, valid_test_case

INVALID_BITLIST_CASES = [
    ("no_delimiter_empty", b""),
    ("no_delimiter_zero_byte", b"\x00"),
    ("no_delimiter_zeroes", b"\x00\x00\x00"),
]


def bitlist_case_fn(
    rng: Random, mode: RandomizationMode, limit: int, force_final_bit: bool | None = None
):
    bits = get_random_ssz_object(
        rng,
        Bitlist[limit],
        max_bytes_length=(limit // 8) + 1,
        max_list_length=limit,
        mode=mode,
        chaos=False,
    )
    if force_final_bit is not None and bits.length() > 0:
        bits[bits.length() - 1] = force_final_bit
    return bits


def valid_cases():
    rng = Random(1234)
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 511, 512, 513]:
        for variation in range(5):
            for mode in [
                RandomizationMode.mode_nil_count,
                RandomizationMode.mode_max_count,
                RandomizationMode.mode_random,
                RandomizationMode.mode_zero,
                RandomizationMode.mode_max,
            ]:
                yield (
                    f"bitlist_{size}_{mode.to_name()}_{variation}",
                    valid_test_case(
                        lambda rng=rng, mode=mode, size=size, variation=variation: bitlist_case_fn(
                            rng, mode, size, force_final_bit=[None, True, False][variation % 3]
                        )
                    ),
                )


def invalid_cases():
    rng = Random(1234)
    for typ_limit, test_limit in [
        (1, 2),
        (1, 7),
        (1, 8),
        (1, 9),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 8),
        (8, 9),
        (32, 64),
        (32, 33),
        (512, 513),
    ]:
        for description, data in INVALID_BITLIST_CASES:
            yield (
                f"bitlist_{typ_limit}_{description}",
                invalid_test_case(Bitlist[typ_limit], lambda data=data: data),
            )
        yield (
            f"bitlist_{typ_limit}_but_{test_limit}",
            invalid_test_case(
                Bitlist[typ_limit],
                lambda rng=rng, test_limit=test_limit: serialize(
                    bitlist_case_fn(rng, RandomizationMode.mode_max_count, test_limit)
                ),
            ),
        )
