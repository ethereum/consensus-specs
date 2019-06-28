from typing import Dict, Iterator
import copy
from types import GeneratorType


class DefaultingTypeMeta(type):
    def default(cls):
        raise Exception("Not implemented")


class SSZType(DefaultingTypeMeta):

    def is_fixed_size(cls):
        raise Exception("Not implemented")


class SSZValue(object, metaclass=SSZType):

    def type(self):
        return self.__class__


class BasicType(SSZType):
    byte_len = 0

    def is_fixed_size(cls):
        return True


class BasicValue(int, SSZValue, metaclass=BasicType):
    pass


class Bool(BasicValue):  # can't subclass bool.
    byte_len = 1

    def __new__(cls, value: int):  # int value, but can be any subclass of int (bool, Bit, Bool, etc...)
        if value < 0 or value > 1:
            raise ValueError(f"value {value} out of bounds for bit")
        return super().__new__(cls, value)

    @classmethod
    def default(cls):
        return cls(0)

    def __bool__(self):
        return self > 0


# Alias for Bool
class Bit(Bool):
    pass


class uint(BasicValue, metaclass=BasicType):

    def __new__(cls, value: int):
        if value < 0:
            raise ValueError("unsigned types must not be negative")
        if cls.byte_len and value.bit_length() > (cls.byte_len << 3):
            raise ValueError("value out of bounds for uint{}".format(cls.byte_len * 8))
        return super().__new__(cls, value)

    def __add__(self, other):
        return self.__class__(super().__add__(coerce_type_maybe(other, self.__class__, strict=True)))

    def __sub__(self, other):
        return self.__class__(super().__sub__(coerce_type_maybe(other, self.__class__, strict=True)))

    @classmethod
    def default(cls):
        return cls(0)


class uint8(uint):
    byte_len = 1


# Alias for uint8
class byte(uint8):
    pass


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


def coerce_type_maybe(v, typ: SSZType, strict: bool = False):
    v_typ = type(v)
    # shortcut if it's already the type we are looking for
    if v_typ == typ:
        return v
    elif isinstance(v, int):
        if isinstance(v, uint):  # do not coerce from one uintX to another uintY
            if issubclass(typ, uint) and v.type().byte_len == typ.byte_len:
                return typ(v)
            # revert to default behavior below if-else. (ValueError/bare)
        else:
            return typ(v)
    elif isinstance(v, (list, tuple)):
        return typ(*v)
    elif isinstance(v, (bytes, BytesN, Bytes)):
        return typ(v)
    elif isinstance(v, GeneratorType):
        return typ(v)

    # just return as-is, Value-checkers will take care of it not being coerced, if we are not strict.
    if strict and not isinstance(v, typ):
        raise ValueError("Type coercion of {} to {} failed".format(v, typ))
    return v


class Series(SSZValue):

    def __iter__(self) -> Iterator[SSZValue]:
        raise Exception("Not implemented")


# Note: importing ssz functionality locally, to avoid import loop

class Container(Series, metaclass=SSZType):

    def __init__(self, **kwargs):
        cls = self.__class__
        for f, t in cls.get_fields().items():
            if f not in kwargs:
                setattr(self, f, t.default())
            else:
                value = coerce_type_maybe(kwargs[f], t)
                if not isinstance(value, t):
                    raise ValueError(f"Bad input for class {self.__class__}:"
                                     f" field: {f} type: {t} value: {value} value type: {type(value)}")
                setattr(self, f, value)

    def serialize(self):
        from .ssz_impl import serialize
        return serialize(self)

    def hash_tree_root(self):
        from .ssz_impl import hash_tree_root
        return hash_tree_root(self)

    def signing_root(self):
        from .ssz_impl import signing_root
        return signing_root(self)

    def __setattr__(self, name, value):
        if name not in self.__class__.__annotations__:
            raise AttributeError("Cannot change non-existing SSZ-container attribute")
        field_typ = self.__class__.__annotations__[name]
        value = coerce_type_maybe(value, field_typ)
        if not isinstance(value, field_typ):
            raise ValueError(f"Cannot set field of {self.__class__}:"
                             f" field: {name} type: {field_typ} value: {value} value type: {type(value)}")
        super().__setattr__(name, value)

    def __repr__(self):
        return repr({field: (getattr(self, field) if hasattr(self, field) else 'unset')
                     for field in self.get_fields().keys()})

    def __str__(self):
        output = [f'{self.__class__.__name__}']
        for field in self.get_fields().keys():
            output.append(f'  {field}: {getattr(self, field)}')
        return "\n".join(output)

    def __eq__(self, other):
        return self.hash_tree_root() == other.hash_tree_root()

    def __hash__(self):
        return hash(self.hash_tree_root())

    def copy(self):
        return copy.deepcopy(self)

    @classmethod
    def get_fields(cls) -> Dict[str, SSZType]:
        if not hasattr(cls, '__annotations__'):  # no container fields
            return {}
        return dict(cls.__annotations__)

    @classmethod
    def default(cls):
        return cls(**{f: t.default() for f, t in cls.get_fields().items()})

    @classmethod
    def is_fixed_size(cls):
        return all(t.is_fixed_size() for t in cls.get_fields().values())

    def __iter__(self) -> Iterator[SSZValue]:
        return iter([getattr(self, field) for field in self.get_fields().keys()])


class ParamsBase(Series):
    _has_params = False

    def __new__(cls, *args, **kwargs):
        if not cls._has_params:
            raise Exception("cannot init bare type without params")
        return super().__new__(cls, **kwargs)


class ParamsMeta(SSZType):

    def __new__(cls, class_name, parents, attrs):
        out = type.__new__(cls, class_name, parents, attrs)
        if hasattr(out, "_has_params") and getattr(out, "_has_params"):
            for k, v in attrs.items():
                setattr(out, k, v)
        return out

    def __getitem__(self, params):
        o = self.__class__(self.__name__, (self,), self.attr_from_params(params))
        return o

    def __str__(self):
        return f"{self.__name__}~{self.__class__.__name__}"

    def __repr__(self):
        return self, self.__class__

    def attr_from_params(self, p):
        # single key params are valid too. Wrap them in a tuple.
        params = p if isinstance(p, tuple) else (p,)
        res = {'_has_params': True}
        i = 0
        for (name, typ) in self.__annotations__.items():
            if hasattr(self.__class__, name):
                res[name] = getattr(self.__class__, name)
            else:
                if i >= len(params):
                    i += 1
                    continue
                param = params[i]
                if not isinstance(param, typ):
                    raise TypeError(
                        "cannot create parametrized class with param {} as {} of type {}".format(param, name, typ))
                res[name] = param
                i += 1
        if len(params) != i:
            raise TypeError("provided parameters {} mismatch required parameter count {}".format(params, i))
        return res

    def __subclasscheck__(self, subclass):
        # check regular class system if we can, solves a lot of the normal cases.
        if super().__subclasscheck__(subclass):
            return True
        # if they are not normal subclasses, they are of the same class.
        # then they should have the same name
        if subclass.__name__ != self.__name__:
            return False
        # If they do have the same name, they should also have the same params.
        for name, typ in self.__annotations__.items():
            if hasattr(self, name) and hasattr(subclass, name) \
                    and getattr(subclass, name) != getattr(self, name):
                return False
        return True

    def __instancecheck__(self, obj):
        return self.__subclasscheck__(obj.__class__)


class ElementsType(ParamsMeta):
    elem_type: SSZType
    length: int


class Elements(ParamsBase, metaclass=ElementsType):
    pass


class BaseList(list, Elements):

    def __init__(self, *args):
        items = self.extract_args(*args)

        if not self.value_check(items):
            raise ValueError(f"Bad input for class {self.__class__}: {items}")
        super().__init__(items)

    @classmethod
    def value_check(cls, value):
        return all(isinstance(v, cls.elem_type) for v in value) and len(value) <= cls.length

    @classmethod
    def extract_args(cls, *args):
        x = list(args)
        if len(x) == 1 and isinstance(x[0], (GeneratorType, list, tuple)):
            x = list(x[0])
        x = [coerce_type_maybe(v, cls.elem_type) for v in x]
        return x

    def __str__(self):
        cls = self.__class__
        return f"{cls.__name__}[{cls.elem_type.__name__}, {cls.length}]({', '.join(str(v) for v in self)})"

    def __getitem__(self, k) -> SSZValue:
        if isinstance(k, int):  # check if we are just doing a lookup, and not slicing
            if k < 0:
                raise IndexError(f"cannot get item in type {self.__class__} at negative index {k}")
            if k > len(self):
                raise IndexError(f"cannot get item in type {self.__class__}"
                                 f" at out of bounds index {k}")
        return super().__getitem__(k)

    def __setitem__(self, k, v):
        if k < 0:
            raise IndexError(f"cannot set item in type {self.__class__} at negative index {k} (to {v})")
        if k > len(self):
            raise IndexError(f"cannot set item in type {self.__class__}"
                             f" at out of bounds index {k} (to {v}, bound: {len(self)})")
        super().__setitem__(k, coerce_type_maybe(v, self.__class__.elem_type, strict=True))

    def append(self, v):
        super().append(coerce_type_maybe(v, self.__class__.elem_type, strict=True))

    def __iter__(self) -> Iterator[SSZValue]:
        return super().__iter__()

    def last(self):
        # be explict about getting the last item, for the non-python readers, and negative-index safety
        return self[len(self) - 1]


class List(BaseList):

    @classmethod
    def default(cls):
        return cls()

    @classmethod
    def is_fixed_size(cls):
        return False


class Vector(BaseList):

    @classmethod
    def value_check(cls, value):
        # check length limit strictly
        return len(value) == cls.length and super().value_check(value)

    @classmethod
    def default(cls):
        return cls(cls.elem_type.default() for _ in range(cls.length))

    @classmethod
    def is_fixed_size(cls):
        return cls.elem_type.is_fixed_size()

    def append(self, v):
        # Deep-copy and other utils like to change the internals during work.
        # Only complain if we had the right size.
        if len(self) == self.__class__.length:
            raise Exception("cannot modify vector length")
        else:
            super().append(v)

    def pop(self, *args):
        raise Exception("cannot modify vector length")


class BytesType(ElementsType):
    elem_type: SSZType = byte
    length: int


class BaseBytes(bytes, Elements, metaclass=BytesType):

    def __new__(cls, *args) -> "BaseBytes":
        extracted_val = cls.extract_args(*args)
        if not cls.value_check(extracted_val):
            raise ValueError(f"Bad input for class {cls}: {extracted_val}")
        return super().__new__(cls, extracted_val)

    @classmethod
    def extract_args(cls, *args):
        x = args
        if len(x) == 1 and isinstance(x[0], (GeneratorType, bytes)):
            x = x[0]
        if isinstance(x, bytes):  # Includes BytesLike
            return x
        else:
            return bytes(x)  # E.g. GeneratorType put into bytes.

    @classmethod
    def value_check(cls, value):
        # check type and virtual length limit
        return isinstance(value, bytes) and len(value) <= cls.length

    def __str__(self):
        cls = self.__class__
        return f"{cls.__name__}[{cls.length}]: {self.hex()}"


class Bytes(BaseBytes):

    @classmethod
    def default(cls):
        return b''

    @classmethod
    def is_fixed_size(cls):
        return False


class BytesN(BaseBytes):

    @classmethod
    def extract_args(cls, *args):
        if len(args) == 0:
            return cls.default()
        else:
            return super().extract_args(*args)

    @classmethod
    def default(cls):
        return b'\x00' * cls.length

    @classmethod
    def value_check(cls, value):
        # check length limit strictly
        return len(value) == cls.length and super().value_check(value)

    @classmethod
    def is_fixed_size(cls):
        return True


# Helpers for common BytesN types.
Bytes4: BytesType = BytesN[4]
Bytes32: BytesType = BytesN[32]
Bytes48: BytesType = BytesN[48]
Bytes96: BytesType = BytesN[96]
