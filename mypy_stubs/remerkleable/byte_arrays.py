from typing import Optional, Any, TypeVar, Type, BinaryIO
from types import GeneratorType
from remerkleable.tree import Node, RootNode, Root, subtree_fill_to_contents, get_depth, to_gindex, \
    subtree_fill_to_length, Gindex, PairNode
from remerkleable.core import View, ViewHook, zero_node, FixedByteLengthViewHelper, pack_bytes_to_chunks, ObjType, \
    ObjParseException
from remerkleable.basic import byte, uint256

V = TypeVar('V', bound=View)


class RawBytesView(bytes, View):
    def __new__(cls, *args, **kwargs):
        if len(args) == 0:
            return super().__new__(cls, cls.default_bytes(), **kwargs)
        elif len(args) == 1:
            args = args[0]
            if isinstance(args, (GeneratorType, list, tuple)):
                data = bytes(args)
            elif isinstance(args, bytes):
                data = args
            elif isinstance(args, str):
                if args[:2] == '0x':
                    args = args[2:]
                data = list(bytes.fromhex(args))
            else:
                data = bytes(args)
            return super().__new__(cls, data, **kwargs)
        else:
            return super().__new__(cls, bytes(args), **kwargs)

    @classmethod
    def default_bytes(cls) -> bytes:
        raise NotImplementedError

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        return cls(v)

    @classmethod
    def tree_depth(cls) -> int:
        raise NotImplementedError

    def set_backing(self, value):
        raise Exception("cannot change the backing of a raw-bytes-like view, init a new view instead")

    def __repr__(self):
        return "0x" + self.hex()

    def __str__(self):
        return "0x" + self.hex()

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        return cls(bytez)

    def encode_bytes(self) -> bytes:
        return self

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, (list, tuple, str, bytes)):
            raise ObjParseException(f"obj '{obj}' is not a list, tuple, str or bytes")
        return cls(obj)

    def to_obj(self) -> ObjType:
        return '0x' + self.encode_bytes().hex()

    def navigate_view(self, key: Any) -> View:
        return byte(self.__getitem__(key))


class ByteVector(RawBytesView, FixedByteLengthViewHelper, View):
    def __new__(cls, *args, **kwargs):
        byte_len = cls.vector_length()
        out = super().__new__(cls, *args, **kwargs)
        if len(out) != byte_len:
            raise Exception(f"incorrect byte length: {len(out)}, expected {byte_len}")
        return out

    def __class_getitem__(cls, length) -> Type["ByteVector"]:
        chunk_count = (length + 31) // 32
        tree_depth = get_depth(chunk_count)

        class SpecialByteVectorView(ByteVector):
            @classmethod
            def default_node(cls) -> Node:
                return subtree_fill_to_length(zero_node(0), tree_depth, chunk_count)

            @classmethod
            def tree_depth(cls) -> int:
                return tree_depth

            @classmethod
            def type_byte_length(cls) -> int:
                return length

        return SpecialByteVectorView

    @classmethod
    def vector_length(cls):
        return cls.type_byte_length()

    @classmethod
    def default_bytes(cls) -> bytes:
        return b"\x00" * cls.vector_length()

    @classmethod
    def type_repr(cls) -> str:
        return f"ByteVector[{cls.vector_length()}]"

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        depth = cls.tree_depth()
        byte_len = cls.vector_length()
        if depth == 0:
            return cls.decode_bytes(node.merkle_root()[:byte_len])
        else:
            chunk_count = (byte_len + 31) // 32
            chunks = [node.getter(to_gindex(i, depth)) for i in range(chunk_count)]
            bytez = b"".join(ch.merkle_root() for ch in chunks)[:byte_len]
            return cls.decode_bytes(bytez)

    def get_backing(self) -> Node:
        if len(self) == 32:  # super common case, optimize for it
            return RootNode(Root(self))
        elif len(self) < 32:
            return RootNode(Root(self + b"\x00" * (32 - len(self))))
        else:
            return subtree_fill_to_contents(pack_bytes_to_chunks(self), self.__class__.tree_depth())

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key < 0 or key > cls.vector_length():
            raise KeyError
        return byte

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        depth = cls.tree_depth()
        byte_len = cls.vector_length()
        if key < 0 or key >= byte_len:
            raise KeyError
        chunk_i = key // 32
        return to_gindex(chunk_i, depth)


# Define common special Byte vector view types, these are bytes-like:
# raw representation instead of backed by a binary tree. Inheriting Python "bytes"
Bytes1 = ByteVector[1]
Bytes4 = ByteVector[4]
Bytes8 = ByteVector[8]
Bytes32 = ByteVector[32]
Bytes48 = ByteVector[48]
Bytes96 = ByteVector[96]


class ByteList(RawBytesView, FixedByteLengthViewHelper, View):

    def __new__(cls, *args, **kwargs):
        byte_limit = cls.limit()
        out = super().__new__(cls, *args, **kwargs)
        if len(out) > byte_limit:
            raise Exception(f"incorrect byte length: {len(out)}, cannot be more than limit {byte_limit}")
        return out

    def __class_getitem__(cls, limit) -> Type["ByteList"]:
        chunk_count = (limit + 31) // 32
        contents_depth = get_depth(chunk_count)

        class SpecialByteListView(ByteList):
            @classmethod
            def contents_depth(cls) -> int:
                return contents_depth

            @classmethod
            def limit(cls) -> int:
                return limit

        return SpecialByteListView

    @classmethod
    def limit(cls) -> int:
        raise NotImplementedError

    @classmethod
    def default_bytes(cls) -> bytes:
        return b""

    @classmethod
    def type_repr(cls) -> str:
        return f"ByteList[{cls.limit()}]"

    @classmethod
    def view_from_backing(cls: Type[V], node: Node, hook: Optional[ViewHook[V]] = None) -> V:
        contents_depth = cls.contents_depth()
        contents_node = node.get_left()
        length = uint256.view_from_backing(node.get_right())
        if length > cls.limit():
            raise Exception("ByteList backing declared length exceeds limit")
        if contents_depth == 0:
            return cls.decode_bytes(contents_node.root[:length])
        else:
            chunk_count = (length + 31) // 32
            chunks = [contents_node.getter(to_gindex(i, contents_depth)) for i in range(chunk_count)]
            bytez = b"".join(ch.root for ch in chunks)[:length]
            return cls.decode_bytes(bytez)

    def get_backing(self) -> Node:
        return PairNode(
            subtree_fill_to_contents(pack_bytes_to_chunks(self), self.__class__.contents_depth()),
            uint256(len(self)).get_backing()
        )

    @classmethod
    def contents_depth(cls) -> int:
        raise NotImplementedError

    @classmethod
    def tree_depth(cls) -> int:
        return cls.contents_depth() + 1  # 1 extra for length mix-in

    @classmethod
    def default_node(cls) -> Node:
        return PairNode(zero_node(cls.contents_depth()), zero_node(0))  # mix-in 0 as list length

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key < 0 or key > cls.limit():
            raise KeyError
        return byte

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        depth = cls.tree_depth()
        byte_limit = cls.limit()
        if key < 0 or key >= byte_limit:
            raise KeyError
        chunk_i = key // 32
        return to_gindex(chunk_i, depth)

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return False

    @classmethod
    def min_byte_length(cls) -> int:
        return 0

    @classmethod
    def max_byte_length(cls) -> int:
        return cls.limit()

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        return cls.decode_bytes(stream.read(scope))

    def value_byte_length(self) -> int:
        return len(self)
