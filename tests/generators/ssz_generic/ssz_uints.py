from ssz_test_case import invalid_test_case, valid_test_case
from eth2spec.utils.ssz.ssz_typing import BasicView, uint8, uint16, uint32, uint64, uint128, uint256
from random import Random
from typing import Type
from eth2spec.debug.random_value import RandomizationMode, get_random_ssz_object


def uint_case_fn(rng: Random, mode: RandomizationMode, typ: Type[BasicView]):
    return get_random_ssz_object(rng, typ,
                                 max_bytes_length=typ.type_byte_length(),
                                 max_list_length=1,
                                 mode=mode, chaos=False)


UINT_TYPES = [uint8, uint16, uint32, uint64, uint128, uint256]


def valid_cases():
    rng = Random(1234)
    for uint_type in UINT_TYPES:
        mode = RandomizationMode.mode_random
        byte_len = uint_type.type_byte_length()
        yield f'uint_{byte_len * 8}_last_byte_empty', \
              valid_test_case(lambda: uint_type((2 ** ((byte_len - 1) * 8)) - 1))
        for variation in range(5):
            yield f'uint_{byte_len * 8}_{mode.to_name()}_{variation}', \
                valid_test_case(lambda: uint_case_fn(rng, mode, uint_type))
        for mode in [RandomizationMode.mode_zero, RandomizationMode.mode_max]:
            yield f'uint_{byte_len * 8}_{mode.to_name()}', \
                valid_test_case(lambda: uint_case_fn(rng, mode, uint_type))


def invalid_cases():
    for uint_type in UINT_TYPES:
        byte_len = uint_type.type_byte_length()
        yield f'uint_{byte_len * 8}_one_too_high', \
            invalid_test_case(lambda: (2 ** (byte_len * 8)).to_bytes(byte_len + 1, 'little'))
    for uint_type in [uint8, uint16, uint32, uint64, uint128, uint256]:
        byte_len = uint_type.type_byte_length()
        yield f'uint_{byte_len * 8}_one_byte_longer', \
              invalid_test_case(lambda: (2 ** (byte_len * 8) - 1).to_bytes(byte_len + 1, 'little'))
    for uint_type in [uint8, uint16, uint32, uint64, uint128, uint256]:
        byte_len = uint_type.type_byte_length()
        yield f'uint_{byte_len * 8}_one_byte_shorter', \
              invalid_test_case(lambda: (2 ** ((byte_len - 1) * 8) - 1).to_bytes(byte_len - 1, 'little'))
