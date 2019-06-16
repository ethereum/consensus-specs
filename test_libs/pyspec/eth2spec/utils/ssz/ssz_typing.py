from typing import Tuple, Dict, Iterator
from types import GeneratorType


class ValueCheckError(Exception):
    pass


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


class Bit(BasicValue):  # can't subclass bool.

    def __new__(cls, value, *args, **kwargs):
        if value < 0 or value > 1:
            raise ValueError(f"value {value} out of bounds for bit")
        return super().__new__(cls, value)

    @classmethod
    def default(cls):
        return cls(False)

    def __bool__(self):
        return self > 0


class uint(BasicValue, metaclass=BasicType):

    def __new__(cls, value, *args, **kwargs):
        if value < 0:
            raise ValueError("unsigned types must not be negative")
        if cls.byte_len and value.bit_length() > (cls.byte_len << 3):
            raise ValueError("value out of bounds for uint{}".format(cls.byte_len))
        return super().__new__(cls, value)

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


class Series(SSZValue):

    def __iter__(self) -> Iterator[SSZValue]:
        raise Exception("Not implemented")


# Note: importing ssz functionality locally, to avoid import loop

class Container(Series, metaclass=SSZType):

    def __init__(self, **kwargs):
        cls = self.__class__
        for f, t in cls.get_fields():
            if f not in kwargs:
                setattr(self, f, t.default())
            else:
                setattr(self, f, kwargs[f])

    def serialize(self):
        from .ssz_impl import serialize
        return serialize(self)

    def hash_tree_root(self):
        from .ssz_impl import hash_tree_root
        return hash_tree_root(self)

    def signing_root(self):
        from .ssz_impl import signing_root
        return signing_root(self)

    def get_field_values(self) -> Tuple[SSZValue, ...]:
        cls = self.__class__
        return tuple(getattr(self, field) for field in cls.get_field_names())

    def __repr__(self):
        return repr({field: getattr(self, field) for field in self.get_field_names()})

    def __str__(self):
        output = [f'{self.__class__.__name__}']
        for field in self.get_field_names():
            output.append(f'  {field}: {getattr(self, field)}')
        return "\n".join(output)

    def __eq__(self, other):
        return self.hash_tree_root() == other.hash_tree_root()

    def __hash__(self):
        return hash(self.hash_tree_root())

    @classmethod
    def get_fields_dict(cls) -> Dict[str, SSZType]:
        return dict(cls.__annotations__)

    @classmethod
    def get_fields(cls) -> Tuple[Tuple[str, SSZType], ...]:
        return tuple((f, t) for f, t in cls.__annotations__.items())

    def get_typed_values(self):
        return tuple(zip(self.get_field_values(), self.get_field_types()))

    @classmethod
    def get_field_names(cls) -> Tuple[str]:
        return tuple(cls.__annotations__.keys())

    @classmethod
    def get_field_types(cls) -> Tuple[SSZType, ...]:
        # values of annotations are the types corresponding to the fields, not instance values.
        return tuple(cls.__annotations__.values())

    @classmethod
    def default(cls):
        return cls(**{f: t.default() for f, t in cls.get_fields()})

    @classmethod
    def is_fixed_size(cls):
        return all(t.is_fixed_size() for t in cls.get_field_types())

    def __iter__(self) -> Iterator[SSZValue]:
        return iter(self.get_field_values())


class ParamsBase(Series):
    _bare = True

    def __new__(cls, *args, **kwargs):
        if cls._bare:
            raise Exception("cannot init bare type without params")
        return super().__new__(cls, **kwargs)


class ParamsMeta(SSZType):

    def __new__(cls, class_name, parents, attrs):
        out = type.__new__(cls, class_name, parents, attrs)
        for k, v in attrs.items():
            setattr(out, k, v)
        return out

    def __getitem__(self, params):
        o = self.__class__(self.__name__, (self,), self.attr_from_params(params))
        o._bare = False
        return o

    def __str__(self):
        return f"{self.__name__}~{self.__class__.__name__}"

    def __repr__(self):
        return self, self.__class__

    def attr_from_params(self, p):
        # single key params are valid too. Wrap them in a tuple.
        params = p if isinstance(p, tuple) else (p,)
        res = {}
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

    def __instancecheck__(self, obj):
        if obj.__class__.__name__ != self.__name__:
            return False
        for name, typ in self.__annotations__.items():
            if hasattr(self, name) and hasattr(obj.__class__, name) \
                    and getattr(obj.__class__, name) != getattr(self, name):
                return False
        return True


class Elements(ParamsMeta):
    elem_type: SSZType
    length: int


class ElementsBase(ParamsBase, metaclass=Elements):

    def __init__(self, *args):
        items = self.extract_args(*args)

        if not self.value_check(items):
            raise ValueCheckError(f"Bad input for class {self.__class__}: {items}")
        self.items = items

    @classmethod
    def value_check(cls, value):
        return all(isinstance(v, cls.elem_type) for v in value)

    @classmethod
    def extract_args(cls, *args):
        x = list(args)
        if len(x) == 1 and isinstance(x[0], GeneratorType):
            x = list(x[0])
        return x

    def __str__(self):
        cls = self.__class__
        return f"{cls.__name__}[{cls.elem_type.__name__}, {cls.length}]({', '.join(str(v) for v in self.items)})"

    def __getitem__(self, i) -> SSZValue:
        return self.items[i]

    def __setitem__(self, k, v):
        self.items[k] = v

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        return repr(self.items)

    def __iter__(self) -> Iterator[SSZValue]:
        return iter(self.items)

    def __eq__(self, other):
        return self.items == other.items


class List(ElementsBase):

    @classmethod
    def default(cls):
        return cls()

    @classmethod
    def is_fixed_size(cls):
        return False


class Vector(ElementsBase):

    @classmethod
    def value_check(cls, value):
        return len(value) == cls.length and super().value_check(value)

    @classmethod
    def default(cls):
        return [cls.elem_type.default() for _ in range(cls.length)]

    @classmethod
    def is_fixed_size(cls):
        return cls.elem_type.is_fixed_size()


class BytesMeta(Elements):
    elem_type: SSZType = byte
    length: int


class BytesLike(ElementsBase, metaclass=BytesMeta):

    @classmethod
    def extract_args(cls, args):
        if isinstance(args, bytes):
            return args
        elif isinstance(args, BytesLike):
            return args.items
        elif isinstance(args, GeneratorType):
            return bytes(args)
        else:
            return bytes(args)

    @classmethod
    def value_check(cls, value):
        return isinstance(value, bytes)

    def __str__(self):
        cls = self.__class__
        return f"{cls.__name__}[{cls.length}]: {self.items.hex()}"


class Bytes(BytesLike):

    @classmethod
    def default(cls):
        return b''

    @classmethod
    def is_fixed_size(cls):
        return False


class BytesN(BytesLike):

    @classmethod
    def default(cls):
        return b'\x00' * cls.length

    @classmethod
    def value_check(cls, value):
        return len(value) == cls.length and super().value_check(value)

    @classmethod
    def is_fixed_size(cls):
        return True
