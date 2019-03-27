from typing import Any, List, NewType

from constants import SLOTS_PER_EPOCH, SHARD_COUNT, TARGET_COMMITTEE_SIZE, SHUFFLE_ROUND_COUNT
from utils import hash
from yaml_objects import Validator

Epoch = NewType("Epoch", int)
ValidatorIndex = NewType("ValidatorIndex", int)
Bytes32 = NewType("Bytes32", bytes)


def int_to_bytes1(x):
    return x.to_bytes(1, 'little')


def int_to_bytes4(x):
    return x.to_bytes(4, 'little')


def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, 'little')


def is_active_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch


def get_active_validator_indices(validators: List[Validator], epoch: Epoch) -> List[ValidatorIndex]:
    """
    Get indices of active validators from ``validators``.
    """
    return [i for i, v in enumerate(validators) if is_active_validator(v, epoch)]


def split(values: List[Any], split_count: int) -> List[List[Any]]:
    """
    Splits ``values`` into ``split_count`` pieces.
    """
    list_length = len(values)
    return [
        values[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    ]


def get_epoch_committee_count(active_validator_count: int) -> int:
    """
    Return the number of committees in one epoch.
    """
    return max(
        1,
        min(
            SHARD_COUNT // SLOTS_PER_EPOCH,
            active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
            )
    ) * SLOTS_PER_EPOCH


def get_permuted_index(index: int, list_size: int, seed: Bytes32) -> int:
    """
    Return `p(index)` in a pseudorandom permutation `p` of `0...list_size-1` with ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
    for round in range(SHUFFLE_ROUND_COUNT):
        pivot = bytes_to_int(hash(seed + int_to_bytes1(round))[0:8]) % list_size
        flip = (pivot - index) % list_size
        position = max(index, flip)
        source = hash(seed + int_to_bytes1(round) + int_to_bytes4(position // 256))
        byte = source[(position % 256) // 8]
        bit = (byte >> (position % 8)) % 2
        index = flip if bit else index

    return index


def get_shuffling(seed: Bytes32,
                  validators: List[Validator],
                  epoch: Epoch) -> List[List[ValidatorIndex]]:
    """
    Shuffle active validators and split into crosslink committees.
    Return a list of committees (each a list of validator indices).
    """
    # Shuffle active validator indices
    active_validator_indices = get_active_validator_indices(validators, epoch)
    length = len(active_validator_indices)
    shuffled_indices = [active_validator_indices[get_permuted_index(i, length, seed)] for i in range(length)]

    # Split the shuffled active validator indices
    return split(shuffled_indices, get_epoch_committee_count(length))
