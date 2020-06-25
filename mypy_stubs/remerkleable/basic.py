from typing import Any, TypeVar, Type
from remerkleable.core import BasicView, View, ObjType, ObjParseException

V = TypeVar('V', bound=View)


# Not returning "NotImplemented" like regular operators,
# it's completely invalid, do not let the interpreter resort to the other operation hand.
class OperationNotSupported(Exception):
    pass


class boolean(int, BasicView):

    def encode_bytes(self) -> bytes:
        return b"\x01" if self else b"\x00"

    def __new__(cls, value: int):  # int value, but can be any subclass of int (bool, Bit, Bool, etc...)
        if value < 0 or value > 1:
            raise ValueError(f"value {value} out of bounds for bit")
        return super().__new__(cls, value)

    def __add__(self, other):
        raise OperationNotSupported(f"cannot add bool ({self} + {other})")

    def __sub__(self, other):
        raise OperationNotSupported(f"cannot sub bool ({self} - {other})")

    def __mul__(self, other):
        raise OperationNotSupported(f"cannot mul bool ({self} * {other})")

    def __floordiv__(self, other):  # Better known as "//"
        raise OperationNotSupported(f"cannot floordiv bool ({self} // {other})")

    def __truediv__(self, other):
        raise OperationNotSupported(f"cannot truediv bool ({self} / {other})")

    def __bool__(self):
        return self > 0

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        return cls(v)

    @classmethod
    def type_byte_length(cls) -> int:
        return 1

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        return cls(bytez != b"\x00")

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, bool):
            raise ObjParseException(f"obj '{obj}' is not a bool")
        return cls(obj)

    def to_obj(self) -> ObjType:
        return bool(self)

    @classmethod
    def type_repr(cls) -> str:
        return "boolean"


T = TypeVar('T', bound="uint")


class uint(int, BasicView):
    def __new__(cls, value: int):
        if value < 0:
            raise ValueError(f"unsigned type {cls} must not be negative")
        byte_len = cls.type_byte_length()
        if value.bit_length() > (byte_len << 3):
            raise ValueError(f"value out of bounds for {cls}")
        return super().__new__(cls, value)

    def __add__(self: T, other: int) -> T:
        return self.__class__(super().__add__(self.__class__.coerce_view(other)))

    def __radd__(self: T, other: int) -> T:
        return self.__add__(other)

    def __sub__(self: T, other: int) -> T:
        return self.__class__(super().__sub__(self.__class__.coerce_view(other)))

    def __rsub__(self: T, other: int) -> T:
        return self.__class__(self.__class__.coerce_view(other).__sub__(self))

    def __mul__(self: T, other: int) -> T:
        return self.__class__(super().__mul__(self.__class__.coerce_view(other)))

    def __rmul__(self: T, other: int) -> T:
        return self.__mul__(other)

    def __mod__(self: T, other: int) -> T:
        return self.__class__(super().__mod__(self.__class__.coerce_view(other)))

    def __rmod__(self: T, other: int) -> T:
        return self.__class__(self.__class__.coerce_view(other).__mod__(self))

    def __floordiv__(self: T, other: int) -> T:  # Better known as "//"
        return self.__class__(super().__floordiv__(self.__class__.coerce_view(other)))

    def __rfloordiv__(self: T, other: int) -> T:
        return self.__class__(self.__class__.coerce_view(other).__floordiv__(self))

    def __truediv__(self: T, other: int) -> T:
        raise OperationNotSupported(f"non-integer division '{self} / {other}' "
                                    f"is not valid for {self.__class__.type_repr()} left hand type")

    def __rtruediv__(self: T, other: int) -> T:
        raise OperationNotSupported(f"non-integer division '{other} / {self}' "
                                    f"is not valid for {self.__class__.type_repr()} right hand type")

    def __pow__(self: T, other: int, modulo=None) -> T:
        return self.__class__(super().__pow__(other, modulo))  # TODO: stricter argument checks?

    def __rpow__(self: T, other, modulo=None) -> T:
        return self.__class__(super().__rpow__(other, modulo))  # TODO: see __pow__

    def __lshift__(self: T, other: int) -> T:
        """Left bitshift clips bits at uint boundary"""
        mask = (1 << (self.type_byte_length() << 3)) - 1
        return self.__class__(super().__lshift__(int(other)) & mask)

    def __rlshift__(self: T, other: int) -> T:
        raise OperationNotSupported(f"{other} << {self} through __rlshift__ is not supported, "
                                    f"{other} must be a uint type with __lshift__")

    def __rshift__(self: T, other: int) -> T:
        return self.__class__(super().__rshift__(int(other)))

    def __rrshift__(self: T, other: int) -> T:
        raise OperationNotSupported(f"{other} >> {self} through __rrshift__ is not supported, "
                                    f"{other} must be a uint type with __rshift__")

    def __and__(self: T, other: int) -> T:
        return self.__class__(super().__and__(self.__class__.coerce_view(other)))

    def __rand__(self: T, other: int) -> T:
        return self.__and__(other)

    def __xor__(self: T, other: int) -> T:
        return self.__class__(super().__xor__(self.__class__.coerce_view(other)))

    def __rxor__(self: T, other: int) -> T:
        return self.__xor__(other)

    def __or__(self: T, other: int) -> T:
        return self.__class__(super().__or__(self.__class__.coerce_view(other)))

    def __ror__(self: T, other: int) -> T:
        return self.__or__(other)

    def __neg__(self):
        raise OperationNotSupported(f"Cannot make uint type negative! If intentional, cast to signed int first.")

    def __invert__(self: T) -> T:
        mask = (1 << (self.type_byte_length() << 3)) - 1
        return self.__xor__(mask)

    def __pos__(self: T) -> T:
        return self

    def __abs__(self: T) -> T:
        return self

    # __coerce__ is avoided to utilize explicit type hinting and special case the edge-cases for unsigned int safety

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        if isinstance(v, uint) and cls.type_byte_length() != v.__class__.type_byte_length():
            raise ValueError("value must have equal byte length to coerce it")
        if isinstance(v, bytes):
            return cls.decode_bytes(v)
        return cls(v)

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        return cls(int.from_bytes(bytez, byteorder='little'))

    def encode_bytes(self) -> bytes:
        return self.to_bytes(length=self.__class__.type_byte_length(), byteorder='little')

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, (int, str)):
            raise ObjParseException(f"obj '{obj}' is not an int or str")
        if isinstance(obj, str):
            if obj.startswith('0x'):
                return cls.decode_bytes(bytes.fromhex(obj[2:]))
            obj = int(obj)
        return cls(obj)

    def to_obj(self) -> ObjType:
        return int(self)

    @classmethod
    def type_repr(cls) -> str:
        return f"uint{cls.type_byte_length()*8}"


class uint8(uint):
    @classmethod
    def type_byte_length(cls) -> int:
        return 1


class uint16(uint):
    @classmethod
    def type_byte_length(cls) -> int:
        return 2


class uint32(uint):
    @classmethod
    def type_byte_length(cls) -> int:
        return 4


class uint64(uint):
    @classmethod
    def type_byte_length(cls) -> int:
        return 8

    # JSON encoder should be able to handle uint64, converting it to a string if necessary.
    # no "to_obj" here.


class uint128(uint):
    @classmethod
    def type_byte_length(cls) -> int:
        return 16

    def to_obj(self) -> ObjType:
        return "0x" + self.encode_bytes().hex()


class uint256(uint):
    @classmethod
    def type_byte_length(cls) -> int:
        return 32

    def to_obj(self) -> ObjType:
        return "0x" + self.encode_bytes().hex()


class bit(boolean):
    pass


class byte(uint8):
    pass
