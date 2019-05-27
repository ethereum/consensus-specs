from random import Random
from typing import Any
from enum import Enum

from eth2spec.utils.ssz.ssz_typing import *
from eth2spec.utils.ssz.ssz_impl import is_basic_type

# in bytes
UINT_SIZES = [1, 2, 4, 8, 16, 32]

random_mode_names = ["random", "zero", "max", "nil", "one", "lengthy"]


class RandomizationMode(Enum):
    # random content / length
    mode_random = 0
    # Zero-value
    mode_zero = 1
    # Maximum value, limited to count 1 however
    mode_max = 2
    # Return 0 values, i.e. empty
    mode_nil_count = 3
    # Return 1 value, random content
    mode_one_count = 4
    # Return max amount of values, random content
    mode_max_count = 5

    def to_name(self):
        return random_mode_names[self.value]

    def is_changing(self):
        return self.value in [0, 4, 5]


def get_random_ssz_object(rng: Random,
                          typ: Any,
                          max_bytes_length: int,
                          max_list_length: int,
                          mode: RandomizationMode,
                          chaos: bool) -> Any:
    """
    Create an object for a given type, filled with random data.
    :param rng: The random number generator to use.
    :param typ: The type to instantiate
    :param max_bytes_length: the max. length for a random bytes array
    :param max_list_length: the max. length for a random list
    :param mode: how to randomize
    :param chaos: if true, the randomization-mode will be randomly changed
    :return: the random object instance, of the given type.
    """
    if chaos:
        mode = rng.choice(list(RandomizationMode))
    # Bytes array
    if is_bytes_type(typ):
        if mode == RandomizationMode.mode_nil_count:
            return b''
        if mode == RandomizationMode.mode_max_count:
            return get_random_bytes_list(rng, max_bytes_length)
        if mode == RandomizationMode.mode_one_count:
            return get_random_bytes_list(rng, 1)
        if mode == RandomizationMode.mode_zero:
            return b'\x00'
        if mode == RandomizationMode.mode_max:
            return b'\xff'
        return get_random_bytes_list(rng, rng.randint(0, max_bytes_length))
    elif is_bytesn_type(typ):
        length = typ.length
        # Sanity, don't generate absurdly big random values
        # If a client is aiming to performance-test, they should create a benchmark suite.
        assert length <= max_bytes_length
        if mode == RandomizationMode.mode_zero:
            return b'\x00' * length
        if mode == RandomizationMode.mode_max:
            return b'\xff' * length
        return get_random_bytes_list(rng, length)
    # Basic types
    elif is_basic_type(typ):
        if mode == RandomizationMode.mode_zero:
            return get_min_basic_value(typ)
        if mode == RandomizationMode.mode_max:
            return get_max_basic_value(typ)
        return get_random_basic_value(rng, typ)
    # Vector:
    elif is_vector_type(typ):
        elem_typ = read_vector_elem_type(typ)
        return [
            get_random_ssz_object(rng, elem_typ, max_bytes_length, max_list_length, mode, chaos)
            for _ in range(typ.length)
        ]
    # List:
    elif is_list_type(typ):
        elem_typ = read_list_elem_type(typ)
        length = rng.randint(0, max_list_length)
        if mode == RandomizationMode.mode_one_count:
            length = 1
        if mode == RandomizationMode.mode_max_count:
            length = max_list_length
        return [
            get_random_ssz_object(rng, elem_typ, max_bytes_length, max_list_length, mode, chaos)
            for _ in range(length)
        ]
    # Container:
    elif is_container_type(typ):
        return typ(**{
            field:
                get_random_ssz_object(rng, subtype, max_bytes_length, max_list_length, mode, chaos)
                for field, subtype in typ.get_fields()
        })
    else:
        print(typ)
        raise Exception("Type not recognized")


def get_random_bytes_list(rng: Random, length: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(length))


def get_random_basic_value(rng: Random, typ: str) -> Any:
    if is_bool_type(typ):
        return rng.choice((True, False))
    if is_uint_type(typ):
        size = uint_byte_size(typ)
        assert size in UINT_SIZES
        return rng.randint(0, 256**size - 1)
    else:
        raise ValueError("Not a basic type")


def get_min_basic_value(typ: str) -> Any:
    if is_bool_type(typ):
        return False
    if is_uint_type(typ):
        size = uint_byte_size(typ)
        assert size in UINT_SIZES
        return 0
    else:
        raise ValueError("Not a basic type")


def get_max_basic_value(typ: str) -> Any:
    if is_bool_type(typ):
        return True
    if is_uint_type(typ):
        size = uint_byte_size(typ)
        assert size in UINT_SIZES
        return 256**size - 1
    else:
        raise ValueError("Not a basic type")
