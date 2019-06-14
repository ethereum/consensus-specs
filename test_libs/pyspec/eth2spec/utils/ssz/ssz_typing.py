from types import GeneratorType
from typing import List, Iterable, TypeVar, Type, NewType
from typing import Union
from typing_inspect import get_origin

# SSZ integers
# -----------------------------

class uint(int):
    byte_len = 0

    def __new__(cls, value, *args, **kwargs):
        if value < 0:
            raise ValueError("unsigned types must not be negative")
        if value.byte_len and value.bit_length() > value.byte_len:
            raise ValueError("value out of bounds for uint{}".format(value.byte_len))
        return super().__new__(cls, value)


class uint8(uint):
    byte_len = 1

# Alias for uint8
byte = NewType('byte', uint8)

class uint16(uint):
    byte_len = 2

class uint32(uint):
    byte_len = 4

class uint64(uint):
    byte_len = 8

class uint128(uint):
    byte_len = 16

class uint256(uint):
    byte_len = 32

def is_uint_type(typ):
    # All integers are uint in the scope of the spec here.
    # Since we default to uint64. Bounds can be checked elsewhere.
    # However, some are wrapped in a NewType
    if hasattr(typ, '__supertype__'):
        # get the type that the NewType is wrapping
        typ = typ.__supertype__

    return isinstance(typ, type) and issubclass(typ, int) and not issubclass(typ, bool)

# SSZ Container base class
# -----------------------------

# Note: importing ssz functionality locally, to avoid import loop

class Container(object):

    def __init__(self, **kwargs):
        cls = self.__class__
        for f, t in cls.get_fields():
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

    def get_field_values(self):
        cls = self.__class__
        return [getattr(self, field) for field in cls.get_field_names()]

    def __repr__(self):
        return repr({field: getattr(self, field) for field in self.get_field_names()})

    def __str__(self):
        output = []
        for field in self.get_field_names():
            output.append(f'{field}: {getattr(self, field)}')
        return "\n".join(output)

    def __eq__(self, other):
        return self.hash_tree_root() == other.hash_tree_root()

    def __hash__(self):
        return hash(self.hash_tree_root())

    @classmethod
    def get_fields_dict(cls):
        return dict(cls.__annotations__)

    @classmethod
    def get_fields(cls):
        return list(dict(cls.__annotations__).items())

    def get_typed_values(self):
        return list(zip(self.get_field_values(), self.get_field_types()))

    @classmethod
    def get_field_names(cls):
        return list(cls.__annotations__.keys())

    @classmethod
    def get_field_types(cls):
        # values of annotations are the types corresponding to the fields, not instance values.
        return list(cls.__annotations__.values())


def get_zero_value(typ):
    if typ == int:
        return 0
    elif is_container_type(typ):
        return typ(**{f: get_zero_value(t) for f, t in typ.get_fields()})
    else:
        return typ.default()

def type_check(typ, value):
    if typ == int or typ == uint64:
        return isinstance(value, int)
    else:
        return typ.value_check(value)

class AbstractListMeta(type):
    def __new__(cls, class_name, parents, attrs):
        out = type.__new__(cls, class_name, parents, attrs)
        if 'elem_type' in attrs and 'length' in attrs:
            setattr(out, 'elem_type', attrs['elem_type'])
            setattr(out, 'length', attrs['length'])
        return out

    def __getitem__(self, params):
        if not isinstance(params, tuple) or len(params) != 2:
            raise Exception("List must be instantiated with two args: elem type and length")
        o = self.__class__(self.__name__, (self,), {'elem_type': params[0], 'length': params[1]})
        o._name = 'AbstractList'
        return o

    def __instancecheck__(self, obj):
        if obj.__class__.__name__ != self.__name__:
            return False
        if hasattr(self, 'elem_type') and obj.__class__.elem_type != self.elem_type:
            return False
        if hasattr(self, 'length') and obj.__class__.length != self.length:
            return False
        return True

class ValueCheckError(Exception):
    pass

class AbstractList(metaclass=AbstractListMeta):
    def __init__(self, *args):
        items = self.extract_args(args)
            
        if not self.value_check(items):
            raise ValueCheckError("Bad input for class {}: {}".format(self.__class__, items))
        self.items = items
    
    def value_check(self, value):
        for v in value:
            if not type_check(self.__class__.elem_type, v):
                return False
        return True

    def extract_args(self, args):
        return list(args) if len(args) > 0 else self.default()

    def default(self):
        raise Exception("Not implemented")

    def __getitem__(self, i):
        return self.items[i]

    def __setitem__(self, k, v):
        self.items[k] = v

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        return repr(self.items)

    def __iter__(self):
        return iter(self.items)

    def __eq__(self, other):
        return self.items == other.items

class List(AbstractList, metaclass=AbstractListMeta):
    def value_check(self, value):
        return len(value) <= self.__class__.length and super().value_check(value)

    def default(self):
        return []

class Vector(AbstractList, metaclass=AbstractListMeta):
    def value_check(self, value):
        return len(value) == self.__class__.length and super().value_check(value)

    def default(self):
        return [get_zero_value(self.__class__.elem_type) for _ in range(self.__class__.length)]

class BytesMeta(AbstractListMeta):
    def __getitem__(self, params):
        if not isinstance(params, int):
            raise Exception("Bytes must be instantiated with one arg: length")
        o = self.__class__(self.__name__, (self,), {'length': params})
        o._name = 'Bytes'
        return o

def single_item_extractor(cls, args):
    assert len(args) < 2
    return args[0] if len(args) > 0 else cls.default()

class Bytes(AbstractList, metaclass=BytesMeta):
    def value_check(self, value):
        return len(value) <= self.__class__.length and isinstance(value, bytes)

    extract_args = single_item_extractor

    def default(self):
        return b''

class BytesN(AbstractList, metaclass=BytesMeta):
    def value_check(self, value):
        return len(value) == self.__class__.length and isinstance(value, bytes)

    extract_args = single_item_extractor

    def default(self):
        return b'\x00' * self.__class__.length


# Type helpers
# -----------------------------

def infer_type(obj):
    if is_uint_type(obj.__class__):
        return obj.__class__
    elif isinstance(obj, int):
        return uint64
    elif isinstance(obj, (List, Vector, Container, bool, BytesN, Bytes)):
        return obj.__class__
    else:
        raise Exception("Unknown type for {}".format(obj))


def infer_input_type(fn):
    """
    Decorator to run infer_type on the obj if typ argument is None
    """
    def infer_helper(obj, typ=None, **kwargs):
        if typ is None:
            typ = infer_type(obj)
        return fn(obj, typ=typ, **kwargs)
    return infer_helper


def is_bool_type(typ):
    """
    Check if the given type is a bool.
    """
    if hasattr(typ, '__supertype__'):
        typ = typ.__supertype__
    return isinstance(typ, type) and issubclass(typ, bool)


def is_list_type(typ):
    """
    Check if the given type is a list.
    """
    return isinstance(typ, type) and issubclass(typ, List)


def is_bytes_type(typ):
    """
    Check if the given type is a ``bytes``.
    """
    return isinstance(typ, type) and issubclass(typ, Bytes)


def is_bytesn_type(typ):
    """
    Check if the given type is a BytesN.
    """
    return isinstance(typ, type) and issubclass(typ, BytesN)


def is_list_kind(typ):
    """
    Check if the given type is a kind of list. Can be bytes.
    """
    return is_list_type(typ) or is_bytes_type(typ)


def is_vector_type(typ):
    """
    Check if the given type is a vector.
    """
    return isinstance(typ, type) and issubclass(typ, Vector)


def is_vector_kind(typ):
    """
    Check if the given type is a kind of vector. Can be BytesN.
    """
    return is_vector_type(typ) or is_bytesn_type(typ)


def is_container_type(typ):
    """
    Check if the given type is a container.
    """
    return isinstance(typ, type) and issubclass(typ, Container)


T = TypeVar('T')
L = TypeVar('L')


def read_elem_type(typ):
    return typ.elem_type
