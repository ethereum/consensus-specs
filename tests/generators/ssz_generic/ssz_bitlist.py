from ssz_test_case import invalid_test_case, valid_test_case
from eth2spec.utils.ssz.ssz_typing import Bitlist
from eth2spec.utils.ssz.ssz_impl import serialize
from random import Random
from eth2spec.debug.random_value import RandomizationMode, get_random_ssz_object


def bitlist_case_fn(rng: Random, mode: RandomizationMode, limit: int):
    return get_random_ssz_object(
        rng,
        Bitlist[limit],
        max_bytes_length=(limit // 8) + 1,
        max_list_length=limit,
        mode=mode,
        chaos=False,
    )


def valid_cases():
    rng = Random(1234)
    for size in [1, 2, 3, 4, 5, 8, 16, 31, 512, 513]:
        for variation in range(5):
            for mode in [
                RandomizationMode.mode_nil_count,
                RandomizationMode.mode_max_count,
                RandomizationMode.mode_random,
                RandomizationMode.mode_zero,
                RandomizationMode.mode_max,
            ]:
                yield f"bitlist_{size}_{mode.to_name()}_{variation}", valid_test_case(
                    lambda: bitlist_case_fn(rng, mode, size)
                )


def invalid_cases():
    yield "bitlist_no_delimiter_empty", invalid_test_case(lambda: b"")
    yield "bitlist_no_delimiter_zero_byte", invalid_test_case(lambda: b"\x00")
    yield "bitlist_no_delimiter_zeroes", invalid_test_case(lambda: b"\x00\x00\x00")
    rng = Random(1234)
    for typ_limit, test_limit in [
        (1, 2),
        (1, 8),
        (1, 9),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (8, 9),
        (32, 64),
        (32, 33),
        (512, 513),
    ]:
        yield f"bitlist_{typ_limit}_but_{test_limit}", invalid_test_case(
            lambda: serialize(bitlist_case_fn(rng, RandomizationMode.mode_max_count, test_limit))
        )
