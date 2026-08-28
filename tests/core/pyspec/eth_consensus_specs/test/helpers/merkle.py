from ssz.proofs import build_proof, get_generalized_index as _get_generalized_index
from ssz.ssz_base import SSZType
from ssz.uint import BaseUint

__all__ = ["build_proof", "get_generalized_index"]


def get_generalized_index(ssz_type: type[SSZType], *path: str | int) -> int:
    """
    Position in a Merkle tree of the value a path selects.

    An element position given as a uint is passed on as a plain number. The
    library reads a path by weighing each step against the words it reserves
    for a length or a layout, and a uint refuses to be weighed against a word.
    """
    steps = (int(step) if isinstance(step, BaseUint) else step for step in path)
    return _get_generalized_index(ssz_type, *steps)
