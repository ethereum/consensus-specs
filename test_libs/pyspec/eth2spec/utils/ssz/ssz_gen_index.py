from .ssz_math import next_power_of_two, previous_power_of_two
from .ssz_typing import (
    SSZType, BasicValue, ComplexType,
    ElementsType, Container, List, ByteList, uint64,
    Bitlist
)
from .ssz_impl import item_length, chunk_count
from typing import Union, Tuple, Sequence

# Just an alias to the trusty Python big int; generalized indices are not serialized, they are just for processing.
GeneralizedIndex = int


def get_item_position(typ: SSZType, index: Union[int, str]) -> Tuple[int, int, int]:
    """
    Returns three variables: (i) the index of the chunk in which the given element of the item is
    represented, (ii) the starting byte position within the chunk, (iii) the ending byte position within the chunk.
    For example for a 6-item list of uint64 values, index=2 will return (0, 16, 24), index=5 will return (1, 8, 16)
    """
    if isinstance(typ, ElementsType):
        start = index * item_length(typ.elem_type)
        return start // 32, start % 32, start % 32 + item_length(typ.elem_type)
    elif issubclass(typ, Container):
        return typ.get_field_names().index(index), 0, item_length(get_elem_type(typ, index))
    else:
        raise Exception("Only lists/vectors/containers supported")


def get_elem_type(typ: ComplexType, index: Union[int, str]) -> SSZType:
    """
    Returns the type of the element of an object of the given type with the given index
    or member variable name (eg. `7` for `x[7]`, `"foo"` for `x.foo`)
    """
    if issubclass(typ, Container):
        return typ.get_fields()[index]
    elif isinstance(typ, ElementsType):
        return typ.elem_type
    else:
        raise Exception("Only Containers and series of Elements can have an indexed element type")


def get_generalized_index(typ: SSZType, path: List[Union[int, str]]) -> GeneralizedIndex:
    """
    Converts a path (eg. `[7, "foo", 3]` for `x[7].foo[3]`, `[12, "bar", "__len__"]` for
    `len(x[12].bar)`) into the generalized index representing its position in the Merkle tree.
    """
    root = 1
    for p in path:
        assert not issubclass(typ, BasicValue)  # If we descend to a basic type, the path cannot continue further
        if p == '__len__':
            typ, root = uint64, root * 2 + 1 if issubclass(typ, (List, ByteList, Bitlist)) else None
        else:
            pos, _, _ = get_item_position(typ, p)
            if issubclass(typ, (List, ByteList, Bitlist)):
               root *= 2  # bit for length mix in
            root *= next_power_of_two(chunk_count(typ)) + pos
            typ = get_elem_type(typ, p)
    return root


# Generalized index helpers


def concat_generalized_indices(*indices: GeneralizedIndex) -> GeneralizedIndex:
    """
    Given generalized indices i1 for A -> B, i2 for B -> C .... i_n for Y -> Z, returns
    the generalized index for A -> Z.
    """
    o = GeneralizedIndex(1)
    for i in indices:
        o = o * previous_power_of_two(i) + (i - previous_power_of_two(i))
    return o


def get_generalized_index_length(index: GeneralizedIndex) -> int:
    """
    Returns the length of a path represented by a generalized index.
    """
    return index.bit_length() - 1


def get_generalized_index_bit(index: GeneralizedIndex, position: int) -> bool:
    """
    Returns the given bit of a generalized index.
    """
    return (index & (1 << position)) > 0


def generalized_index_sibling(index: GeneralizedIndex) -> GeneralizedIndex:
    return index ^ 1


def generalized_index_child(index: GeneralizedIndex, right_side: bool) -> GeneralizedIndex:
    return (index << 1) | right_side


def generalized_index_parent(index: GeneralizedIndex) -> GeneralizedIndex:
    return index >> 1

