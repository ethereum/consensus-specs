from typing import Callable, Optional, Any, cast, List as PyList, BinaryIO,\
    TypeVar, Type, Protocol, runtime_checkable, Union

# noinspection PyUnresolvedReferences
from typing import _ProtocolMeta

from remerkleable.tree import Node, Root, RootNode, zero_node, concat_gindices, Gindex
from itertools import zip_longest
from typing import Iterable, Tuple

OFFSET_BYTE_LENGTH = 4


V = TypeVar('V', bound="View")


class TypeDefMeta(_ProtocolMeta):
    def __truediv__(self, other) -> "Path":
        return Path.from_raw_path(anchor=cast(Type[View], self), path=[other])


ObjType = Union[dict, list, tuple, str, int, bool, None, "ObjType"]


class ObjParseException(Exception):
    pass


@runtime_checkable
class TypeDef(Protocol, metaclass=TypeDefMeta):
    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        ...

    @classmethod
    def default(cls: Type[V], hook: Optional["ViewHook[V]"]) -> V:
        ...

    @classmethod
    def default_node(cls) -> Node:
        ...

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional["ViewHook[V]"] = None) -> V:
        ...

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        ...

    @classmethod
    def type_byte_length(cls) -> int:
        ...

    @classmethod
    def min_byte_length(cls) -> int:
        ...

    @classmethod
    def max_byte_length(cls) -> int:
        ...

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        ...

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        ...

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        ...

    @classmethod
    def type_repr(cls) -> str:
        ...

    @classmethod
    def navigate_type(cls, key: Any) -> Type["View"]:
        raise Exception(f"cannot type-navigate into a {cls.type_repr()}, key: '{key}'")

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        raise Exception(f"cannot get static gindex into type {cls.type_repr()}, key: '{key}'")


class Path(object):
    anchor: Type["View"]
    path: PyList[Tuple[Any, Type["View"]]]  # (key, type) tuples.

    def __init__(self, anchor: Type["View"], path: Optional[PyList[Tuple[Any, Type["View"]]]] = None):
        self.anchor = anchor
        if path is None:
            self.path = []
        else:
            self.path = path

    @staticmethod
    def from_raw_path(anchor: Type["View"], path: PyList[Any]) -> "Path":
        parsed_path = []
        t = anchor
        for step in path:
            t = t.navigate_type(step)
            parsed_path.append((step, t))
        return Path(anchor=anchor, path=parsed_path)

    def __truediv__(self, other) -> "Path":
        if isinstance(other, Path):
            return Path(anchor=self.anchor, path=self.path + other.path)
        else:
            last = self.anchor if len(self.path) == 0 else self.path[-1][1]
            return Path(anchor=self.anchor, path=self.path + [(other, last.navigate_type(other))])

    def gindex(self, view: Optional["View"] = None) -> Gindex:
        step_gindices = []
        if view is None:
            type_end: Type[View] = self.anchor
            for step, typ in self.path:
                gindex = type_end.key_to_static_gindex(step)
                step_gindices.append(gindex)
                type_end = typ
        else:
            view_end: View = view
            for step, _ in self.path:
                gindex = view_end.key_to_dynamic_gindex(step)
                step_gindices.append(gindex)
                view_end = view_end.navigate_view(step)
        return concat_gindices(step_gindices)

    def navigate_type(self) -> Type["View"]:
        return self.path[-1][1]

    def navigate_view(self, v: "View") -> "View":
        for step, _ in self.path:
            v = v.navigate_view(step)
        return v


HV = TypeVar('HV', bound="View")
ViewHook = Callable[[HV], None]


class View(TypeDef):

    @classmethod
    def default(cls: Type[V], hook: Optional[ViewHook[V]]) -> V:
        return cls.view_from_backing(cls.default_node(), hook)

    def get_backing(self) -> Node:
        raise NotImplementedError

    def set_backing(self, value):
        raise NotImplementedError

    def copy(self: V) -> V:
        return self.__class__.view_from_backing(self.get_backing())

    @classmethod
    def type_byte_length(cls) -> int:
        raise Exception("type is dynamic length, or misses overrides. Cannot get type byte length.")

    def value_byte_length(self) -> int:
        raise NotImplementedError

    def __bytes__(self):
        return self.encode_bytes()

    def encode_bytes(self) -> bytes:
        raise NotImplementedError

    def serialize(self, stream: BinaryIO) -> int:
        out = self.encode_bytes()
        stream.write(out)
        return len(out)

    def to_obj(self) -> ObjType:
        raise NotImplementedError

    def navigate_view(self, key: Any) -> "View":
        raise Exception(f"cannot view-navigate into {self}, key: '{key}'")

    def key_to_dynamic_gindex(self, key: Any) -> Gindex:
        return self.__class__.key_to_static_gindex(key)

    def hash_tree_root(self) -> Root:
        return self.get_backing().merkle_root()

    def __eq__(self, other):
        # TODO: should we check types here?
        if not isinstance(other, View):
            other = self.__class__.coerce_view(other)
        return self.hash_tree_root() == other.hash_tree_root()

    def __hash__(self):
        return hash(self.hash_tree_root())


class FixedByteLengthViewHelper(View):
    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return True

    @classmethod
    def min_byte_length(cls) -> int:
        return cls.type_byte_length()

    @classmethod
    def max_byte_length(cls) -> int:
        return cls.type_byte_length()

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        n = cls.type_byte_length()
        if n != scope:
            raise Exception(f"scope {scope} is not valid for expected byte length {n}")
        return cls.decode_bytes(stream.read(n))

    def value_byte_length(self) -> int:
        return self.type_byte_length()


class BackedView(View, TypeDef):
    _hook: Optional[ViewHook]
    _backing: Node

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        return cls(backing=node, hook=hook)

    def __new__(cls, backing: Optional[Node] = None, hook: Optional[ViewHook[V]] = None, **kwargs):
        if backing is None:
            backing = cls.default_node()
        out = super().__new__(cls, **kwargs)
        out._backing = backing
        out._hook = hook
        return out

    def get_backing(self) -> Node:
        return self._backing

    def set_backing(self, value):
        self._backing = value
        # Propagate up the change if the view is hooked to a super view
        if self._hook is not None:
            self._hook(self)


BV = TypeVar('BV', bound="BasicView")


@runtime_checkable
class BasicTypeDef(TypeDef, Protocol):
    @classmethod
    def basic_view_from_backing(cls: Type[BV], node: Node, i: int) -> BV:
        ...

    @classmethod
    def pack_views(cls: Type[BV], views: PyList[BV]) -> PyList[Node]:
        ...


class BasicView(FixedByteLengthViewHelper, BasicTypeDef):
    @classmethod
    def default_node(cls) -> Node:
        return zero_node(0)

    @classmethod
    def view_from_backing(cls: Type[BV], node: Node, hook: Optional[ViewHook[BV]] = None) -> V:
        size = cls.type_byte_length()
        return cls.decode_bytes(node.root[0:size])

    @classmethod
    def basic_view_from_backing(cls: Type[BV], node: Node, i: int) -> BV:
        size = cls.type_byte_length()
        return cls.decode_bytes(node.root[i*size:(i+1)*size])

    @classmethod
    def pack_views(cls: Type[BV], views: PyList[BV]) -> PyList[Node]:
        return list(pack_ints_to_chunks((cast(int, v) for v in views), 32 // cls.type_byte_length()))

    def copy(self: V) -> V:
        return self  # basic views do not have to be copied, they are immutable

    def backing_from_base(self, base: Node, i: int) -> Node:
        section_bytez = self.encode_bytes()
        chunk_bytez = base.root[:len(section_bytez)*i] + section_bytez + base.root[len(section_bytez)*(i+1):]
        return RootNode(Root(chunk_bytez))

    def get_backing(self) -> Node:
        bytez = self.encode_bytes()
        return RootNode(Root(bytez + b"\x00" * (32 - len(bytez))))

    def set_backing(self, value):
        raise Exception("cannot change the backing of a basic view")


# recipe from more-itertools, should have been in itertools really.
def grouper(items: Iterable, n: int, fillvalue=None) -> Iterable[Tuple]:
    """Collect data into fixed-length chunks or blocks
       grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"""
    args = [iter(items)] * n
    # The *same* iterator is referenced n times, thus zip produces tuples of n elements from the same iterator
    return zip_longest(*args, fillvalue=fillvalue)


def pack_ints_to_chunks(items: Iterable[int], items_per_chunk: int) -> PyList[Node]:
    item_byte_len = 32 // items_per_chunk
    return [RootNode(Root(b"".join(v.to_bytes(length=item_byte_len, byteorder='little') for v in chunk_elems)))
            for chunk_elems in grouper(items, items_per_chunk, fillvalue=0)]


def bits_to_byte_int(byte: Tuple[bool, bool, bool, bool, bool, bool, bool, bool]) -> int:
    return sum([byte[i] << i for i in range(0, 8)])


def byte_int_to_byte(b: int) -> bytes:
    return b.to_bytes(length=1, byteorder='little')


def pack_bits_to_chunks(items: Iterable[bool]) -> PyList[Node]:
    return pack_byte_ints_to_chunks(map(bits_to_byte_int, grouper(items, 8, fillvalue=0)))


def pack_byte_ints_to_chunks(items: Iterable[int]) -> PyList[Node]:
    return [RootNode(Root(b"".join(map(byte_int_to_byte, chunk_bytes))))
            for chunk_bytes in grouper(items, 32, fillvalue=0)]


def pack_bytes_to_chunks(bytez: bytes) -> PyList[Node]:
    full_chunks_byte_len = (len(bytez) >> 5) << 5
    out = [RootNode(Root(bytez[i:i+32])) for i in range(0, full_chunks_byte_len, 32)]
    if len(bytez) != full_chunks_byte_len:
        out.append(RootNode(Root(bytez[full_chunks_byte_len:] + (b"\x00" * (32 - (len(bytez) - full_chunks_byte_len))))))
    return out
