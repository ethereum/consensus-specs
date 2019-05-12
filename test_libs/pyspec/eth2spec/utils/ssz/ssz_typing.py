from typing import Generic, List, TypeVar, Type, Iterable, NewType

# SSZ base length, to limit length generic type param of vector/bytesN
SSZLenAny = type('SSZLenAny', (), {})


def SSZLen(length: int):
    """
    SSZ length factory. Creates a type corresponding to a given length. To be used as parameter in type generics.
    """
    assert length >= 0
    typ = type('SSZLen_%d' % length, (SSZLenAny,), {})
    typ.length = length
    return typ


# SSZ element type
T = TypeVar('T')
# SSZ vector/bytesN length
L = TypeVar('L', bound=SSZLenAny)


# SSZ vector
# -----------------------------

class Vector(Generic[T, L]):
    def __init__(self, *args: Iterable[T]):
        self.items = list(args)

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key, value):
        self.items[key] = value

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)


def read_vec_elem_typ(vec_typ: Type[Vector[T,L]]) -> T:
    assert vec_typ.__args__ is not None
    return vec_typ.__args__[0]


def read_vec_len(vec_typ: Type[Vector[T,L]]) -> int:
    assert vec_typ.__args__ is not None
    return vec_typ.__args__[1].length


# SSZ list
# -----------------------------
def read_list_elem_typ(list_typ: Type[List[T]]) -> T:
    assert list_typ.__args__ is not None
    return list_typ.__args__[0]


# SSZ bytesN
# -----------------------------
class BytesN(Generic[L]):
    pass


def read_bytesN_len(bytesN_typ: Type[BytesN[L]]) -> int:
    assert bytesN_typ.__args__ is not None
    return bytesN_typ.__args__[0].length


# SSZ integer types, with 0 computational overhead (NewType)
# -----------------------------

uint8 = NewType('uint8', int)
uint8.byte_len = 1
uint16 = NewType('uint16', int)
uint16.byte_len = 2
uint32 = NewType('uint32', int)
uint32.byte_len = 4
uint64 = NewType('uint64', int)
uint64.byte_len = 8
uint128 = NewType('uint128', int)
uint128.byte_len = 16
uint256 = NewType('uint256', int)
uint256.byte_len = 32
byte = NewType('byte', uint8)


# SSZ Container base class
# -----------------------------

# Note: importing ssz functionality locally, to avoid import loop

class SSZContainer(object):

    def __init__(self, **kwargs):
        from .ssz_impl import get_zero_value
        for f, t in self.__annotations__.items():
            if f not in kwargs:
                setattr(self, f, get_zero_value(t))
            else:
                setattr(self, f, kwargs[f])

    def serialize(self):
        from .ssz_impl import serialize
        return serialize(self, self.__class__)

    def hash_tree_root(self):
        from .ssz_impl import hash_tree_root
        return hash_tree_root(self, self.__class__)

    def signing_root(self):
        from .ssz_impl import signing_root
        return signing_root(self, self.__class__)

