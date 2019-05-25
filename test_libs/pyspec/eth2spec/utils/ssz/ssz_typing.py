from typing import List, Iterable, TypeVar, Type, NewType
from typing import Union
from inspect import isclass

T = TypeVar('T')
L = TypeVar('L')



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
        cls = self.__class__
        for f, t in cls.get_fields().items():
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

    @classmethod
    def get_fields(cls):
        return dict(cls.__annotations__)

    @classmethod
    def get_field_names(cls):
        return list(cls.__annotations__.keys())

    @classmethod
    def get_field_types(cls):
        # values of annotations are the types corresponding to the fields, not instance values.
        return list(cls.__annotations__.values())


def is_uint(typ):
    # Note: only the type reference exists,
    #  but it really resolves to 'int' during run-time for zero computational/memory overhead.
    # Hence, we check equality to the type references (which are really just 'NewType' instances),
    #  and don't use any sub-classing like we normally would.
    return typ == uint8 or typ == uint16 or typ == uint32 or typ == uint64 \
           or typ == uint128 or typ == uint256 or typ == byte

# SSZ vector
# -----------------------------


def _is_vector_instance_of(a, b):
    if not hasattr(b, 'elem_type') or not hasattr(b, 'length'):
        # Vector (b) is not an instance of Vector[X, Y] (a)
        return False
    if not hasattr(a, 'elem_type') or not hasattr(a, 'length'):
        # Vector[X, Y] (b) is an instance of Vector (a)
        return True

    # Vector[X, Y] (a) is an instance of Vector[X, Y] (b)
    return a.elem_type == b.elem_type and a.length == b.length


def _is_equal_vector_type(a, b):
    if not hasattr(a, 'elem_type') or not hasattr(a, 'length'):
        if not hasattr(b, 'elem_type') or not hasattr(b, 'length'):
            # Vector == Vector
            return True
        # Vector != Vector[X, Y]
        return False
    if not hasattr(b, 'elem_type') or not hasattr(b, 'length'):
        # Vector[X, Y] != Vector
        return False
    # Vector[X, Y] == Vector[X, Y]
    return a.elem_type == b.elem_type and a.length == b.length


class VectorMeta(type):
    def __new__(cls, class_name, parents, attrs):
        out = type.__new__(cls, class_name, parents, attrs)
        if 'elem_type' in attrs and 'length' in attrs:
            setattr(out, 'elem_type', attrs['elem_type'])
            setattr(out, 'length', attrs['length'])
        return out

    def __getitem__(self, params):
        if not isinstance(params, tuple) or len(params) != 2:
            raise Exception("Vector must be instantiated with two args: elem type and length")
        o = self.__class__(self.__name__, (Vector,), {'elem_type': params[0], 'length': params[1]})
        o._name = 'Vector'
        return o

    def __subclasscheck__(self, sub):
        return _is_vector_instance_of(self, sub)

    def __instancecheck__(self, other):
        return _is_vector_instance_of(self, other.__class__)

    def __eq__(self, other):
        return _is_equal_vector_type(self, other)

    def __ne__(self, other):
        return not _is_equal_vector_type(self, other)


class Vector(metaclass=VectorMeta):

    def __init__(self, *args: Iterable[T]):

        cls = self.__class__
        if not hasattr(cls, 'elem_type'):
            raise TypeError("Type Vector without elem_type data cannot be instantiated")
        if not hasattr(cls, 'length'):
            raise TypeError("Type Vector without length data cannot be instantiated")

        if len(args) != cls.length:
            if len(args) == 0:
                args = [get_zero_value(cls.elem_type) for _ in range(cls.length)]
            else:
                raise TypeError("Typed vector with length %d cannot hold %d items" % (cls.length, len(args)))

        self.items = list(args)

        # cannot check non-class objects
        if isclass(cls.elem_type):
            for i, item in enumerate(self.items):
                if not isinstance(item, cls.elem_type):
                    raise TypeError("Typed vector cannot hold differently typed value"
                                    " at index %d. Got type: %s, expected type: %s" % (i, type(item), cls.elem_type))

    def serialize(self):
        from .ssz_impl import serialize
        return serialize(self, self.__class__)

    def hash_tree_root(self):
        from .ssz_impl import hash_tree_root
        return hash_tree_root(self, self.__class__)

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key, value):
        self.items[key] = value

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)


def _is_bytes_n_instance_of(a, b):
    if not hasattr(b, 'length'):
        # BytesN (b) is not an instance of BytesN[X] (a)
        return False
    if not hasattr(a, 'length'):
        # BytesN[X] (b) is an instance of BytesN (a)
        return True

    # BytesN[X] (a) is an instance of BytesN[X] (b)
    return a.length == b.length


def _is_equal_bytes_n_type(a, b):
    if not hasattr(a, 'length'):
        if not hasattr(b, 'length'):
            # BytesN == BytesN
            return True
        # BytesN != BytesN[X]
        return False
    if not hasattr(b, 'length'):
        # BytesN[X] != BytesN
        return False
    # BytesN[X] == BytesN[X]
    return a.length == b.length


class BytesNMeta(type):
    def __new__(cls, class_name, parents, attrs):
        out = type.__new__(cls, class_name, parents, attrs)
        if 'length' in attrs:
            setattr(out, 'length', attrs['length'])
        out._name = 'Vector'
        out.elem_type = byte
        return out

    def __getitem__(self, n):
        return self.__class__(self.__name__, (BytesN,), {'length': n})

    def __subclasscheck__(self, sub):
        return _is_bytes_n_instance_of(self, sub)

    def __instancecheck__(self, other):
        return _is_bytes_n_instance_of(self, other.__class__)

    def __eq__(self, other):
        return _is_equal_bytes_n_type(self, other)

    def __ne__(self, other):
        return not _is_equal_bytes_n_type(self, other)


def parse_bytes(val):
    if val is None:
        return None
    if isinstance(val, str):
        # TODO: import from eth-utils instead, and do: hexstr_if_str(to_bytes, val)
        return None
    if isinstance(val, bytes):
        return val
    if isinstance(val, int):
        return bytes([val])
    return None


class BytesN(bytes, metaclass=BytesNMeta):
    def __new__(cls, *args):
        if not hasattr(cls, 'length'):
            return
        bytesval = None
        if len(args) == 1:
            val: Union[bytes, int, str] = args[0]
            bytesval = parse_bytes(val)
        elif len(args) > 1:
            # TODO: each int is 1 byte, check size, create bytesval
            bytesval = bytes(args)

        if bytesval is None:
            if cls.length == 0:
                bytesval = b''
            else:
                bytesval = b'\x00' * cls.length
        if len(bytesval) != cls.length:
            raise TypeError("bytesN[%d] cannot be initialized with value of %d bytes" % (cls.length, len(bytesval)))
        return super().__new__(cls, bytesval)

    def serialize(self):
        from .ssz_impl import serialize
        return serialize(self, self.__class__)

    def hash_tree_root(self):
        from .ssz_impl import hash_tree_root
        return hash_tree_root(self, self.__class__)

# SSZ Defaults
# -----------------------------

def get_zero_value(typ):
    if is_uint(typ):
        return 0
    if issubclass(typ, bool):
        return False
    if issubclass(typ, list):
        return []
    if issubclass(typ, Vector):
        return typ()
    if issubclass(typ, BytesN):
        return typ()
    if issubclass(typ, bytes):
        return b''
    if issubclass(typ, SSZContainer):
        return typ(**{f: get_zero_value(t) for f, t in typ.get_fields().items()}),

# Type helpers
# -----------------------------

def infer_type(obj):
    if is_uint(obj.__class__):
        return obj.__class__
    elif isinstance(obj, int):
        return uint64
    elif isinstance(obj, list):
        return List[infer_type(obj[0])]
    elif isinstance(obj, (Vector, SSZContainer, bool, BytesN, bytes)):
        return obj.__class__
    else:
        raise Exception("Unknown type for {}".format(obj))

def is_list_type(typ):
    return (hasattr(typ, '_name') and typ._name == 'List') or typ == bytes

def is_vector_type(typ):
    return hasattr(typ, '_name') and typ._name == 'Vector'

def is_container_typ(typ):
    return hasattr(typ, 'get_fields')

def read_list_elem_typ(list_typ: Type[List[T]]) -> T:
    assert list_typ.__args__ is not None
    return list_typ.__args__[0]

def read_vector_elem_typ(vector_typ: Type[Vector[T, L]]) -> T:
    return vector_typ.elem_type

def read_elem_typ(typ):
    if typ == bytes:
        return byte
    elif is_list_type(typ):
        return read_list_elem_typ(typ)
    elif is_vector_type(typ):
        return read_vector_elem_typ(typ)
    else:
        raise Exception("Unexpected type: {}".format(typ))
