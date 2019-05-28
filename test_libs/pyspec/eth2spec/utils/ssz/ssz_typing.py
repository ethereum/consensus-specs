from inspect import isclass
from typing import List, Iterable, TypeVar, Type, NewType
from typing import Union
from typing_inspect import get_origin

T = TypeVar('T')
L = TypeVar('L')


# SSZ integers
# -----------------------------

class uint(int):
    byte_len = 0
    def __new__(cls, value, *args, **kwargs):
        if value < 0:
            raise ValueError("unsigned types must not be negative")
        return super().__new__(cls, value)


class uint8(uint):
    byte_len = 1
    def __new__(cls, value, *args, **kwargs):
        if value.bit_length() > 8:
            raise ValueError("value out of bounds for uint8")
        return super().__new__(cls, value)

# Alias for uint8
byte = NewType('byte', uint8)


class uint16(uint):
    byte_len = 2
    def __new__(cls, value, *args, **kwargs):
        if value.bit_length() > 16:
            raise ValueError("value out of bounds for uint16")
        return super().__new__(cls, value)


class uint32(uint):
    byte_len = 4
    def __new__(cls, value, *args, **kwargs):
        if value.bit_length() > 32:
            raise ValueError("value out of bounds for uint16")
        return super().__new__(cls, value)


# We simply default to uint64. But do give it a name, for readability
uint64 = NewType('uint64', int)


class uint128(uint):
    byte_len = 16
    def __new__(cls, value, *args, **kwargs):
        if value.bit_length() > 128:
            raise ValueError("value out of bounds for uint128")
        return super().__new__(cls, value)


class uint256(uint):
    byte_len = 32
    def __new__(cls, value, *args, **kwargs):
        if value.bit_length() > 256:
            raise ValueError("value out of bounds for uint256")
        return super().__new__(cls, value)


def is_uint_type(typ):
    # All integers are uint in the scope of the spec here.
    # Since we default to uint64. Bounds can be checked elsewhere.
    # However, some are wrapped in a NewType
    if hasattr(typ, '__supertype__'):
        # get the type that the NewType is wrapping
        typ = typ.__supertype__

    return isinstance(typ, type) and issubclass(typ, int) and not issubclass(typ, bool)


def uint_byte_size(typ):
    if hasattr(typ, '__supertype__'):
        typ = typ.__supertype__
    if isinstance(typ, type):
        if issubclass(typ, uint):
            return typ.byte_len
        elif issubclass(typ, int):
            # Default to uint64
            return 8
    raise TypeError("Type %s is not an uint (or int-default uint64) type" % typ)


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


# SSZ vector
# -----------------------------


def _is_vector_instance_of(a, b):
    # Other must not be a BytesN
    if issubclass(b, bytes):
        return False
    if not hasattr(b, 'elem_type') or not hasattr(b, 'length'):
        # Vector (b) is not an instance of Vector[X, Y] (a)
        return False
    if not hasattr(a, 'elem_type') or not hasattr(a, 'length'):
        # Vector[X, Y] (b) is an instance of Vector (a)
        return True

    # Vector[X, Y] (a) is an instance of Vector[X, Y] (b)
    return a.elem_type == b.elem_type and a.length == b.length


def _is_equal_vector_type(a, b):
    # Other must not be a BytesN
    if issubclass(b, bytes):
        return False
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

    def __hash__(self):
        return hash(self.__class__)


class Vector(metaclass=VectorMeta):

    def __init__(self, *args: Iterable):

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

    def __repr__(self):
        return repr({'length': self.__class__.length, 'items': self.items})

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key, value):
        self.items[key] = value

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __eq__(self, other):
        return self.hash_tree_root() == other.hash_tree_root()


def _is_bytes_n_instance_of(a, b):
    # Other has to be a Bytes derivative class to be a BytesN
    if not issubclass(b, bytes):
        return False
    if not hasattr(b, 'length'):
        # BytesN (b) is not an instance of BytesN[X] (a)
        return False
    if not hasattr(a, 'length'):
        # BytesN[X] (b) is an instance of BytesN (a)
        return True

    # BytesN[X] (a) is an instance of BytesN[X] (b)
    return a.length == b.length


def _is_equal_bytes_n_type(a, b):
    # Other has to be a Bytes derivative class to be a BytesN
    if not issubclass(b, bytes):
        return False
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
        out._name = 'BytesN'
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

    def __hash__(self):
        return hash(self.__class__)


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
            raise TypeError("BytesN[%d] cannot be initialized with value of %d bytes" % (cls.length, len(bytesval)))
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
    result = None
    if is_uint_type(typ):
        result = 0
    elif is_list_type(typ):
        result = []
    elif issubclass(typ, bool):
        result = False
    elif issubclass(typ, Vector):
        result = typ()
    elif issubclass(typ, BytesN):
        result = typ()
    elif issubclass(typ, bytes):
        result = b''
    elif issubclass(typ, Container):
        result = typ(**{f: get_zero_value(t) for f, t in typ.get_fields()})
    else:
       return Exception("Type not supported: {}".format(typ))
    return result

# Type helpers
# -----------------------------

def infer_type(obj):
    if is_uint_type(obj.__class__):
        return obj.__class__
    elif isinstance(obj, int):
        return uint64
    elif isinstance(obj, list):
        return List[infer_type(obj[0])]
    elif isinstance(obj, (Vector, Container, bool, BytesN, bytes)):
        return obj.__class__
    else:
        raise Exception("Unknown type for {}".format(obj))


def infer_input_type(fn):
    """
    Decorator to run infer_type on the obj if typ argument is None
    """
    def infer_helper(obj, *args, typ=None, **kwargs):
        if typ is None:
            typ = infer_type(obj)
        return fn(obj, *args, typ=typ, **kwargs)
    return infer_helper


def is_bool_type(typ):
    if hasattr(typ, '__supertype__'):
        typ = typ.__supertype__
    return isinstance(typ, type) and issubclass(typ, bool)


def is_list_type(typ):
    """
    Checks if the given type is a list.
    """
    return get_origin(typ) is List or get_origin(typ) is list


def is_bytes_type(typ):
    # Do not accept subclasses of bytes here, to avoid confusion with BytesN
    return typ == bytes


def is_list_kind(typ):
    """
    Checks if the given type is a kind of list. Can be bytes.
    """
    return is_list_type(typ) or is_bytes_type(typ)


def is_vector_type(typ):
    """
    Checks if the given type is a vector.
    """
    return isinstance(typ, type) and issubclass(typ, Vector)


def is_bytesn_type(typ):
    return isinstance(typ, type) and issubclass(typ, BytesN)


def is_vector_kind(typ):
    """
    Checks if the given type is a kind of vector. Can be BytesN.
    """
    return is_vector_type(typ) or is_bytesn_type(typ)


def is_container_type(typ):
    return isinstance(typ, type) and issubclass(typ, Container)


T = TypeVar('T')
L = TypeVar('L')


def read_list_elem_type(list_typ: Type[List[T]]) -> T:
    if list_typ.__args__ is None or len(list_typ.__args__) != 1:
        raise TypeError("Supplied list-type is invalid, no element type found.")
    return list_typ.__args__[0]


def read_vector_elem_type(vector_typ: Type[Vector[T, L]]) -> T:
    return vector_typ.elem_type


def read_elem_type(typ):
    if typ == bytes:
        return byte
    elif is_list_type(typ):
        return read_list_elem_type(typ)
    elif is_vector_type(typ):
        return read_vector_elem_type(typ)
    elif issubclass(typ, bytes):
        return byte
    else:
        raise TypeError("Unexpected type: {}".format(typ))
