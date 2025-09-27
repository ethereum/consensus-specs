from random import Random

from eth2spec.debug.random_value import get_random_ssz_object, RandomizationMode
from eth2spec.utils.ssz.ssz_impl import serialize
from eth2spec.utils.ssz.ssz_typing import Bitvector

from .ssz_test_case import invalid_test_case, valid_test_case


def bitvector_case_fn(
    rng: Random, mode: RandomizationMode, size: int, invalid_making_pos: int = None
):
    bits = get_random_ssz_object(
        rng,
        Bitvector[size],
        max_bytes_length=(size + 7) // 8,
        max_list_length=size,
        mode=mode,
        chaos=False,
    )
    if invalid_making_pos is not None and invalid_making_pos <= size:
        already_invalid = False
        for i in range(invalid_making_pos, size):
            if bits[i]:
                already_invalid = True
        if not already_invalid:
            bits[invalid_making_pos] = True
    return bits


def valid_cases():
    rng = Random(1234)
    for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 511, 512, 513]:
        for mode in [
            RandomizationMode.mode_random,
            RandomizationMode.mode_zero,
            RandomizationMode.mode_max,
        ]:
            yield (
                f"bitvec_{size}_{mode.to_name()}",
                valid_test_case(
                    lambda rng=rng, mode=mode, size=size: bitvector_case_fn(rng, mode, size)
                ),
            )


def invalid_cases():
    # zero length bitvecors are illegal
    yield "bitvec_0", invalid_test_case(Bitvector[1], lambda: b"")
    rng = Random(1234)
    # Create a vector with test_size bits, but make the type typ_size instead,
    # which is invalid when used with the given type size
    # (and a bit set just after typ_size bits if necessary to avoid the valid 0 padding-but-same-last-byte case)
    for typ_size, test_size in [
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (8, 9),
        (9, 8),
        (16, 8),
        (32, 33),
        (512, 513),
    ]:
        for mode in [
            RandomizationMode.mode_random,
            RandomizationMode.mode_zero,
            RandomizationMode.mode_max,
        ]:
            yield (
                f"bitvec_{typ_size}_{mode.to_name()}_{test_size}",
                invalid_test_case(
                    Bitvector[typ_size],
                    lambda rng=rng, mode=mode, test_size=test_size, typ_size=typ_size: serialize(
                        bitvector_case_fn(rng, mode, test_size, invalid_making_pos=typ_size)
                    ),
                ),
            )
