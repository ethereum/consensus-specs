from typing import NewType, Union
from types import GeneratorType


class ValueCheckError(Exception):
    pass


class DefaultingTypeMeta(type):
    def default(cls):
        raise Exception("Not implemented")

# Every type is subclassed and has a default() method, except bool.
TypeWithDefault = Union[DefaultingTypeMeta, bool]


def get_zero_value(typ: TypeWithDefault):
    if issubclass(typ, bool):
        return False
    else:
        return typ.default()


# SSZ integers
# -----------------------------


class uint(int, metaclass=DefaultingTypeMeta):
    byte_len = 0

    def __new__(cls, value, *args, **kwargs):
        if value < 0:
            raise ValueError("unsigned types must not be negative")
        if cls.byte_len and (value.bit_length() >> 3) > cls.byte_len:
            raise ValueError("value out of bounds for uint{}".format(cls.byte_len))
        return super().__new__(cls, value)

    @classmethod
    def default(cls):
        return cls(0)


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


# SSZ Container base class
# -----------------------------

# Note: importing ssz functionality locally, to avoid import loop

class Container(object, metaclass=DefaultingTypeMeta):

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
        output = [f'{self.__class__.__name__}']
        for field in self.get_field_names():
            output.append(f'  {field}: {getattr(self, field)}')
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

    @classmethod
    def default(cls):
        return cls(**{f: get_zero_value(t) for f, t in cls.get_fields()})


class ParamsBase:
    _bare = True

    def __new__(cls, *args, **kwargs):
        if cls._bare:
            raise Exception("cannot init bare type without params")
        return super().__new__(cls, **kwargs)


class ParamsMeta(DefaultingTypeMeta):

    def __new__(cls, class_name, parents, attrs):
        out = type.__new__(cls, class_name, parents, attrs)
        for k, v in attrs.items():
            setattr(out, k, v)
        return out

    def __getitem__(self, params):
        o = self.__class__(self.__name__, (self,), self.attr_from_params(params))
        o._bare = False
        return o

    def attr_from_params(self, p):
        # single key params are valid too. Wrap them in a tuple.
        params = p if isinstance(p, tuple) else (p,)
        res = {}
        i = 0
        for (name, typ) in self.__annotations__.items():
            param = params[i]
            if hasattr(self.__class__, name):
                res[name] = getattr(self.__class__, name)
            else:
                if typ == TypeWithDefault:
                    if not (isinstance(param, bool) or isinstance(param, DefaultingTypeMeta)):
                        raise TypeError("expected param {} as {} to have a type default".format(param, name, typ))
                elif not isinstance(param, typ):
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
        for name, typ in self.__annotations__:
            if hasattr(self, name) and hasattr(obj.__class__, name) \
                    and getattr(obj.__class__, name) != getattr(self, name):
                return False
        return True


class AbstractListMeta(ParamsMeta):
    elem_type: TypeWithDefault
    length: int


class AbstractList(ParamsBase, metaclass=AbstractListMeta):

    def __init__(self, *args):
        items = self.extract_args(*args)

        if not self.value_check(items):
            raise ValueCheckError("Bad input for class {}: {}".format(self.__class__, items))
        self.items = items

    @classmethod
    def value_check(cls, value):
        return all(isinstance(v, cls.elem_type) for v in value)

    @classmethod
    def extract_args(cls, *args):
        x = list(args)
        if len(x) == 1 and isinstance(x[0], GeneratorType):
            x = list(x[0])
        return x if len(x) > 0 else cls.default()

    def __str__(self):
        cls = self.__class__
        return f"{cls.__name__}[{cls.elem_type.__name__}, {cls.length}]({', '.join(str(v) for v in self.items)})"

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


class List(AbstractList):

    @classmethod
    def default(cls):
        return cls()


class Vector(AbstractList, metaclass=AbstractListMeta):

    @classmethod
    def value_check(cls, value):
        return len(value) == cls.length and super().value_check(value)

    @classmethod
    def default(cls):
        return [get_zero_value(cls.elem_type) for _ in range(cls.length)]


class BytesMeta(AbstractListMeta):
    elem_type: TypeWithDefault = byte
    length: int


class BytesLike(AbstractList, metaclass=BytesMeta):

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


class BytesN(BytesLike):

    @classmethod
    def default(cls):
        return b'\x00' * cls.length

    @classmethod
    def value_check(cls, value):
        return len(value) == cls.length and super().value_check(value)

