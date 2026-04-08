from random import Random

from eth_consensus_specs.debug.random_value import get_random_ssz_object, RandomizationMode
from eth_consensus_specs.utils.ssz.ssz_typing import ProgressiveBitlist

from .ssz_bitlist import INVALID_BITLIST_CASES
from .ssz_test_case import invalid_test_case, valid_test_case


def progressive_bitlist_case_fn(
    rng: Random, mode: RandomizationMode, length: int, force_final_bit: bool | None = None
):
    bits = get_random_ssz_object(
        rng,
        ProgressiveBitlist,
        max_bytes_length=(length // 8) + 1,
        max_list_length=length,
        mode=mode,
        chaos=False,
    )
    if force_final_bit is not None and bits.length() > 0:
        bits[bits.length() - 1] = force_final_bit
    return bits


def valid_cases():
    rng = Random(1234)
    random_modes = [
        RandomizationMode.mode_nil_count,
        RandomizationMode.mode_max_count,
        RandomizationMode.mode_random,
        RandomizationMode.mode_zero,
        RandomizationMode.mode_max,
    ]
    for length in [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        15,
        16,
        17,
        31,
        32,
        33,
        63,
        64,
        65,
        255,
        256,
        257,
        511,
        512,
        513,
        1023,
        1024,
        1025,
    ]:
        for variation in range(5):
            for mode in random_modes:
                yield (
                    f"progbitlist_{mode.to_name()}_{length}_{variation}",
                    valid_test_case(
                        lambda rng, mode=mode, length=length, variation=variation: (
                            progressive_bitlist_case_fn(
                                rng,
                                mode,
                                length,
                                force_final_bit=[None, True, False][variation % 3],
                            )
                        ),
                        rng,
                    ),
                )


def invalid_cases():
    for description, data in INVALID_BITLIST_CASES:
        yield (
            f"progbitlist_{description}",
            invalid_test_case(ProgressiveBitlist, lambda data=data: data),
        )
