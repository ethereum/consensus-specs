from .ssz_test_case import invalid_test_case, valid_test_case
from eth2spec.utils.ssz.ssz_typing import Bitvector
from eth2spec.utils.ssz.ssz_impl import serialize
from random import Random
from eth2spec.debug.random_value import RandomizationMode, get_random_ssz_object


def bitvector_case_fn(rng: Random, mode: RandomizationMode, size: int):
    return get_random_ssz_object(rng, Bitvector[size],
                                 max_bytes_length=(size + 7) // 8,
                                 max_list_length=size,
                                 mode=mode, chaos=False)


def valid_cases():
    rng = Random(1234)
    for size in [1, 2, 3, 4, 5, 8, 16, 31, 512, 513]:
        for mode in [RandomizationMode.mode_random, RandomizationMode.mode_zero, RandomizationMode.mode_max]:
            yield f'bitvec_{size}_{mode.to_name()}', valid_test_case(lambda: bitvector_case_fn(rng, mode, size))


def invalid_cases():
    # zero length bitvecors are illegal
    yield 'bitvec_0', lambda: b''
    rng = Random(1234)
    for (typ_size, test_size) in [(1, 2), (2, 3), (3, 4), (4, 5),
                                  (5, 6), (8, 9), (9, 8), (16, 8), (32, 33), (512, 513)]:
        for mode in [RandomizationMode.mode_random, RandomizationMode.mode_zero, RandomizationMode.mode_max]:
            yield f'bitvec_{typ_size}_{mode.to_name()}_{test_size}', \
                  invalid_test_case(lambda: serialize(bitvector_case_fn(rng, mode, test_size)))
