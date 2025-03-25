import random

from eth_utils import (
    to_tuple,
)

import ssz
from ssz.sedes import (
    UInt,
)
from renderers import (
    render_test_case,
)

random.seed(0)


BIT_SIZES = [8, 16, 32, 64, 128, 256]
RANDOM_TEST_CASES_PER_BIT_SIZE = 10
RANDOM_TEST_CASES_PER_LENGTH = 3


def get_random_bytes(length):
    return bytes(random.randint(0, 255) for _ in range(length))


@to_tuple
def generate_random_uint_test_cases():
    for bit_size in BIT_SIZES:
        sedes = UInt(bit_size)

        for _ in range(RANDOM_TEST_CASES_PER_BIT_SIZE):
            value = random.randrange(0, 2**bit_size)
            serial = ssz.encode(value, sedes)
            # note that we need to create the tags in each loop cycle, otherwise ruamel will use
            # YAML references which makes the resulting file harder to read
            tags = tuple(["atomic", "uint", "random"])
            yield render_test_case(
                sedes=sedes,
                valid=True,
                value=value,
                serial=serial,
                tags=tags,
            )


@to_tuple
def generate_uint_wrong_length_test_cases():
    for bit_size in BIT_SIZES:
        sedes = UInt(bit_size)
        lengths = sorted(
            {
                0,
                sedes.length // 2,
                sedes.length - 1,
                sedes.length + 1,
                sedes.length * 2,
            }
        )
        for length in lengths:
            for _ in range(RANDOM_TEST_CASES_PER_LENGTH):
                tags = tuple(["atomic", "uint", "wrong_length"])
                yield render_test_case(
                    sedes=sedes,
                    valid=False,
                    serial=get_random_bytes(length),
                    tags=tags,
                )


@to_tuple
def generate_uint_bounds_test_cases():
    common_tags = ("atomic", "uint")
    for bit_size in BIT_SIZES:
        sedes = UInt(bit_size)

        for value, tag in (
            (0, "uint_lower_bound"),
            (2**bit_size - 1, "uint_upper_bound"),
        ):
            serial = ssz.encode(value, sedes)
            yield render_test_case(
                sedes=sedes,
                valid=True,
                value=value,
                serial=serial,
                tags=common_tags + (tag,),
            )


@to_tuple
def generate_uint_out_of_bounds_test_cases():
    common_tags = ("atomic", "uint")
    for bit_size in BIT_SIZES:
        sedes = UInt(bit_size)

        for value, tag in ((-1, "uint_underflow"), (2**bit_size, "uint_overflow")):
            yield render_test_case(
                sedes=sedes,
                valid=False,
                value=value,
                tags=common_tags + (tag,),
            )
