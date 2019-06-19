from random import Random
from enum import Enum

from eth2spec.utils.ssz.ssz_typing import (
    SSZType, SSZValue, BasicValue, BasicType, uint, Container, Bytes, List, Bit,
    Vector, BytesN
)

# in bytes
UINT_BYTE_SIZES = (1, 2, 4, 8, 16, 32)

random_mode_names = ("random", "zero", "max", "nil", "one", "lengthy")


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
                          typ: SSZType,
                          max_bytes_length: int,
                          max_list_length: int,
                          mode: RandomizationMode,
                          chaos: bool) -> SSZValue:
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
    if issubclass(typ, Bytes):
        # Bytes array
        if mode == RandomizationMode.mode_nil_count:
            return typ(b'')
        elif mode == RandomizationMode.mode_max_count:
            return typ(get_random_bytes_list(rng, max_bytes_length))
        elif mode == RandomizationMode.mode_one_count:
            return typ(get_random_bytes_list(rng, 1))
        elif mode == RandomizationMode.mode_zero:
            return typ(b'\x00')
        elif mode == RandomizationMode.mode_max:
            return typ(b'\xff')
        else:
            return typ(get_random_bytes_list(rng, rng.randint(0, max_bytes_length)))
    elif issubclass(typ, BytesN):
        # Sanity, don't generate absurdly big random values
        # If a client is aiming to performance-test, they should create a benchmark suite.
        assert typ.length <= max_bytes_length
        if mode == RandomizationMode.mode_zero:
            return typ(b'\x00' * typ.length)
        elif mode == RandomizationMode.mode_max:
            return typ(b'\xff' * typ.length)
        else:
            return typ(get_random_bytes_list(rng, typ.length))
    elif issubclass(typ, BasicValue):
        # Basic types
        if mode == RandomizationMode.mode_zero:
            return get_min_basic_value(typ)
        elif mode == RandomizationMode.mode_max:
            return get_max_basic_value(typ)
        else:
            return get_random_basic_value(rng, typ)
    elif issubclass(typ, Vector):
        return typ(
            get_random_ssz_object(rng, typ.elem_type, max_bytes_length, max_list_length, mode, chaos)
            for _ in range(typ.length)
        )
    elif issubclass(typ, List):
        length = rng.randint(0, min(typ.length, max_list_length))
        if mode == RandomizationMode.mode_one_count:
            length = 1
        elif mode == RandomizationMode.mode_max_count:
            length = max_list_length

        return typ(
            get_random_ssz_object(rng, typ.elem_type, max_bytes_length, max_list_length, mode, chaos)
            for _ in range(length)
        )
    elif issubclass(typ, Container):
        # Container
        return typ(**{
            field_name:
                get_random_ssz_object(rng, field_type, max_bytes_length, max_list_length, mode, chaos)
            for field_name, field_type in typ.get_fields().items()
        })
    else:
        raise Exception(f"Type not recognized: typ={typ}")


def get_random_bytes_list(rng: Random, length: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(length))


def get_random_basic_value(rng: Random, typ: BasicType) -> BasicValue:
    if issubclass(typ, Bit):
        return typ(rng.choice((True, False)))
    elif issubclass(typ, uint):
        assert typ.byte_len in UINT_BYTE_SIZES
        return typ(rng.randint(0, 256 ** typ.byte_len - 1))
    else:
        raise ValueError(f"Not a basic type: typ={typ}")


def get_min_basic_value(typ: BasicType) -> BasicValue:
    if issubclass(typ, Bit):
        return typ(False)
    elif issubclass(typ, uint):
        assert typ.byte_len in UINT_BYTE_SIZES
        return typ(0)
    else:
        raise ValueError(f"Not a basic type: typ={typ}")


def get_max_basic_value(typ: BasicType) -> BasicValue:
    if issubclass(typ, Bit):
        return typ(True)
    elif issubclass(typ, uint):
        assert typ.byte_len in UINT_BYTE_SIZES
        return typ(256 ** typ.byte_len - 1)
    else:
        raise ValueError(f"Not a basic type: typ={typ}")
