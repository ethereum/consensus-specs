from random import Random
from typing import Any
from enum import Enum


UINT_SIZES = [8, 16, 32, 64, 128, 256]

basic_types = ["uint%d" % v for v in UINT_SIZES] + ['bool', 'byte']

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
    if isinstance(typ, str):
        # Bytes array
        if typ == 'bytes':
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
        elif typ[:5] == 'bytes' and len(typ) > 5:
            length = int(typ[5:])
            # Sanity, don't generate absurdly big random values
            # If a client is aiming to performance-test, they should create a benchmark suite.
            assert length <= max_bytes_length
            if mode == RandomizationMode.mode_zero:
                return b'\x00' * length
            if mode == RandomizationMode.mode_max:
                return b'\xff' * length
            return get_random_bytes_list(rng, length)
        # Basic types
        else:
            if mode == RandomizationMode.mode_zero:
                return get_min_basic_value(typ)
            if mode == RandomizationMode.mode_max:
                return get_max_basic_value(typ)
            return get_random_basic_value(rng, typ)
    # Vector:
    elif isinstance(typ, list) and len(typ) == 2:
        return [
            get_random_ssz_object(rng, typ[0], max_bytes_length, max_list_length, mode, chaos)
            for _ in range(typ[1])
        ]
    # List:
    elif isinstance(typ, list) and len(typ) == 1:
        length = rng.randint(0, max_list_length)
        if mode == RandomizationMode.mode_one_count:
            length = 1
        if mode == RandomizationMode.mode_max_count:
            length = max_list_length
        return [
            get_random_ssz_object(rng, typ[0], max_bytes_length, max_list_length, mode, chaos)
            for _ in range(length)
        ]
    # Container:
    elif hasattr(typ, 'fields'):
        return typ(**{
            field:
                get_random_ssz_object(rng, subtype, max_bytes_length, max_list_length, mode, chaos)
                for field, subtype in typ.fields.items()
        })
    else:
        print(typ)
        raise Exception("Type not recognized")


def get_random_bytes_list(rng: Random, length: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(length))


def get_random_basic_value(rng: Random, typ: str) -> Any:
    if typ == 'bool':
        return rng.choice((True, False))
    if typ[:4] == 'uint':
        size = int(typ[4:])
        assert size in UINT_SIZES
        return rng.randint(0, 2**size - 1)
    if typ == 'byte':
        return rng.randint(0, 8)
    else:
        raise ValueError("Not a basic type")


def get_min_basic_value(typ: str) -> Any:
    if typ == 'bool':
        return False
    if typ[:4] == 'uint':
        size = int(typ[4:])
        assert size in UINT_SIZES
        return 0
    if typ == 'byte':
        return 0x00
    else:
        raise ValueError("Not a basic type")


def get_max_basic_value(typ: str) -> Any:
    if typ == 'bool':
        return True
    if typ[:4] == 'uint':
        size = int(typ[4:])
        assert size in UINT_SIZES
        return 2**size - 1
    if typ == 'byte':
        return 0xff
    else:
        raise ValueError("Not a basic type")
