from typing import NamedTuple, cast, List as PyList, Dict, Any, BinaryIO, Optional, TypeVar, Type, Protocol, \
    runtime_checkable
from types import GeneratorType
from textwrap import indent
from collections.abc import Sequence as ColSequence
from itertools import chain
import io
from remerkleable.core import View, BasicTypeDef, BasicView, OFFSET_BYTE_LENGTH, ViewHook, ObjType, ObjParseException
from remerkleable.basic import uint256, uint8, uint32
from remerkleable.tree import Node, subtree_fill_to_length, subtree_fill_to_contents,\
    zero_node, Gindex, PairNode, to_gindex, NavigationError, get_depth
from remerkleable.subtree import SubtreeView
from remerkleable.readonly_iters import PackedIter, ComplexElemIter, ComplexFreshElemIter, ContainerElemIter

V = TypeVar('V', bound=View)


def decode_offset(stream: BinaryIO) -> uint32:
    return cast(uint32, uint32.deserialize(stream, OFFSET_BYTE_LENGTH))


def encode_offset(stream: BinaryIO, offset: int):
    return uint32(offset).serialize(stream)


class ComplexView(SubtreeView):
    def encode_bytes(self) -> bytes:
        stream = io.BytesIO()
        self.serialize(stream)
        stream.seek(0)
        return stream.read()

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        stream = io.BytesIO()
        stream.write(bytez)
        stream.seek(0)
        return cls.deserialize(stream, len(bytez))


class MonoSubtreeView(ColSequence, ComplexView):

    def length(self) -> int:
        raise NotImplementedError

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        return cls(*v)

    @classmethod
    def element_cls(cls) -> Type[View]:
        raise NotImplementedError

    @classmethod
    def item_elem_cls(cls, i: int) -> Type[View]:
        return cls.element_cls()

    @classmethod
    def to_chunk_length(cls, elems_length: int) -> int:
        if cls.is_packed():
            elem_type: Type[View] = cls.element_cls()
            if isinstance(elem_type, BasicTypeDef):
                elems_per_chunk = 32 // elem_type.type_byte_length()
                return (elems_length + elems_per_chunk - 1) // elems_per_chunk
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            return elems_length

    @classmethod
    def views_into_chunks(cls, views: PyList[View]) -> PyList[Node]:
        if cls.is_packed():
            elem_type: Type[View] = cls.element_cls()
            if isinstance(elem_type, BasicTypeDef):
                return elem_type.pack_views(views)
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            return [v.get_backing() for v in views]

    @classmethod
    def is_valid_count(cls, count: int) -> bool:
        raise NotImplementedError

    def __iter__(self):
        return iter(self.get(i) for i in range(self.length()))

    def readonly_iter(self):
        tree_depth = self.tree_depth()
        length = self.length()
        backing = self.get_backing()

        elem_type: Type[View] = self.element_cls()

        if self.is_packed():
            return PackedIter(backing, tree_depth, length, cast(Type[BasicView], elem_type))
        else:
            if issubclass(elem_type, bytes):  # is the element type the raw-bytes? Then not re-use views.
                return ComplexFreshElemIter(backing, tree_depth, length, cast(Type[View], elem_type))
            else:
                return ComplexElemIter(backing, tree_depth, length, elem_type)

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        elem_cls = cls.element_cls()
        if elem_cls.is_fixed_byte_length():
            elem_byte_length = elem_cls.type_byte_length()
            if scope % elem_byte_length != 0:
                raise Exception(f"scope {scope} does not match element byte length {elem_byte_length} multiple")
            count = scope // elem_byte_length
            if not cls.is_valid_count(count):
                raise Exception(f"count {count} is invalid")
            return cls(elem_cls.deserialize(stream, elem_byte_length) for _ in range(count))
        else:
            if scope == 0:
                if not cls.is_valid_count(0):
                    raise Exception("scope cannot be 0, count must not be 0")
                return cls()
            first_offset = decode_offset(stream)
            if first_offset > scope:
                raise Exception(f"first offset is too big: {first_offset}, scope: {scope}")
            if first_offset % OFFSET_BYTE_LENGTH != 0:
                raise Exception(f"first offset {first_offset} is not a multiple of offset length {OFFSET_BYTE_LENGTH}")
            count = first_offset // OFFSET_BYTE_LENGTH
            if not cls.is_valid_count(count):
                raise Exception(f"count {count} is invalid")
            # count - 1: we already have the first offset
            offsets = [first_offset] + [decode_offset(stream) for _ in range(count - 1)] + [uint32(scope)]
            elem_min, elem_max = elem_cls.min_byte_length(), elem_cls.max_byte_length()
            elems = []
            for i in range(count):
                start, end = offsets[i], offsets[i+1]
                if end < start:
                    raise Exception(f"offsets[{i}] value {start} is invalid, next offset is {end}")
                elem_size = end - start
                if not (elem_min <= elem_size <= elem_max):
                    raise Exception(f"offset[{i}] value {start} is invalid, next offset is {end},"
                                    f" implied size is {elem_size}, size bounds: [{elem_min}, {elem_max}]")
                elems.append(elem_cls.deserialize(stream, elem_size))
            return cls(*elems)

    def serialize(self, stream: BinaryIO) -> int:
        elem_cls = self.__class__.element_cls()
        if issubclass(elem_cls, uint8):
            out = bytes(iter(self))
            stream.write(out)
            return len(out)
        if elem_cls.is_fixed_byte_length():
            for v in self.readonly_iter():
                v.serialize(stream)
            return elem_cls.type_byte_length() * self.length()
        else:
            temp_dyn_stream = io.BytesIO()
            offset = OFFSET_BYTE_LENGTH * self.length()  # the offsets are part of the fixed-size-bytes prologue
            for v in self:
                encode_offset(stream, offset)
                offset += cast(View, v).serialize(temp_dyn_stream)
            temp_dyn_stream.seek(0)
            stream.write(temp_dyn_stream.read(offset))
            return offset

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, (list, tuple)):
            raise ObjParseException(f"obj '{obj}' is not a list or tuple")
        elem_cls = cls.element_cls()
        return cls(elem_cls.from_obj(el) for el in obj)

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key < 0:
            raise KeyError
        return cls.element_cls()

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        if key < 0:
            raise KeyError

        if cls.is_packed():
            elems_per_chunk = 32 // cls.element_cls().type_byte_length()
            chunk_i = key // elems_per_chunk
        else:
            chunk_i = key

        return to_gindex(chunk_i, cls.tree_depth())

    def navigate_view(self, key: Any) -> View:
        return self.__getitem__(key)

    def __len__(self):
        return self.length()

    def __add__(self, other):
        if issubclass(self.element_cls(), uint8):
            return bytes(self) + bytes(other)
        else:
            return list(chain(self, other))

    def __getitem__(self, k):
        if isinstance(k, slice):
            start = 0 if k.start is None else k.start
            end = self.length() if k.stop is None else k.stop
            return [self.get(i) for i in range(start, end)]
        else:
            return self.get(k)

    def __setitem__(self, k, v):
        if type(k) == slice:
            i = 0 if k.start is None else k.start
            end = self.length() if k.stop is None else k.stop
            for item in v:
                self.set(i, item)
                i += 1
            if i != end:
                raise Exception("failed to do full slice-set, not enough values")
        else:
            self.set(k, v)

    def _repr_sequence(self):
        length: int
        try:
            length = self.length()
        except NavigationError:
            return f"{self.type_repr()}( *summary root, no length known* )"
        vals: Dict[int, View] = {}
        partial = False
        for i in range(length):
            try:
                vals[i] = self.get(i)
            except NavigationError:
                partial = True
                continue
        basic_elems = isinstance(self.element_cls(), BasicTypeDef)
        shortened = length > (64 if basic_elems else 8)
        summary_length = (10 if basic_elems else 3)
        seperator = ', ' if basic_elems else ',\n'
        contents = seperator.join(f"... {length - (summary_length * 2)} omitted ..."
                                  if (shortened and i == summary_length)
                                  else (f"{i}: {repr(v)}" if partial else repr(v))
                                  for i, v in vals.items()
                                  if (not shortened) or i <= summary_length or i >= length - summary_length)
        if '\n' in contents:
            contents = '\n' + indent(contents, '  ') + '\n'
        if partial:
            return f"{self.type_repr()}~partial~<<len={length}>>({contents})"
        else:
            return f"{self.type_repr()}<<len={length}>>({contents})"


class List(MonoSubtreeView):
    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init List")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        elem_cls = cls.element_cls()
        vals = list(args)
        if len(vals) == 1:
            val = vals[0]
            if isinstance(val, (GeneratorType, list, tuple)):
                vals = list(val)
            if issubclass(elem_cls, uint8):
                if isinstance(val, bytes):
                    vals = list(val)
                if isinstance(val, str):
                    if val[:2] == '0x':
                        val = val[2:]
                    vals = list(bytes.fromhex(val))
        if len(vals) > 0:
            limit = cls.limit()
            if len(vals) > limit:
                raise Exception(f"too many list inputs: {len(vals)}, limit is: {limit}")
            input_views = []
            for el in vals:
                if isinstance(el, View):
                    input_views.append(el)
                else:
                    input_views.append(elem_cls.coerce_view(el))
            input_nodes = cls.views_into_chunks(input_views)
            contents = subtree_fill_to_contents(input_nodes, cls.contents_depth())
            backing = PairNode(contents, uint256(len(input_views)).get_backing())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def __class_getitem__(cls, params) -> Type["List"]:
        (element_type, limit) = params
        contents_depth = 0
        packed = False
        if isinstance(element_type, BasicTypeDef):
            elems_per_chunk = 32 // element_type.type_byte_length()
            contents_depth = get_depth((limit + elems_per_chunk - 1) // elems_per_chunk)
            packed = True
        else:
            contents_depth = get_depth(limit)

        class SpecialListView(List):
            @classmethod
            def is_packed(cls) -> bool:
                return packed

            @classmethod
            def contents_depth(cls) -> int:
                return contents_depth

            @classmethod
            def element_cls(cls) -> Type[View]:
                return element_type

            @classmethod
            def limit(cls) -> int:
                return limit

        SpecialListView.__name__ = SpecialListView.type_repr()
        return SpecialListView

    def length(self) -> int:
        ll_node = super().get_backing().get_right()
        ll = cast(uint256, uint256.view_from_backing(node=ll_node, hook=None))
        return int(ll)

    def value_byte_length(self) -> int:
        elem_cls = self.__class__.element_cls()
        if elem_cls.is_fixed_byte_length():
            return elem_cls.type_byte_length() * self.length()
        else:
            return sum(OFFSET_BYTE_LENGTH + cast(View, el).value_byte_length() for el in iter(self))

    def append(self, v: View):
        ll = self.length()
        if ll >= self.__class__.limit():
            raise Exception("list is maximum capacity, cannot append")
        i = ll
        elem_type: Type[View] = self.__class__.element_cls()
        if not isinstance(v, elem_type):
            v = elem_type.coerce_view(v)
        if self.__class__.is_packed():
            next_backing = self.get_backing()
            if isinstance(elem_type, BasicTypeDef):
                if not isinstance(v, BasicView):
                    raise Exception("input element is not a basic view")
                basic_v: BasicView = v
                elems_per_chunk = 32 // elem_type.type_byte_length()
                chunk_i = i // elems_per_chunk
                target: Gindex = to_gindex(chunk_i, self.__class__.tree_depth())
                if i % elems_per_chunk == 0:
                    set_last = next_backing.setter(target, expand=True)
                    chunk = zero_node(0)
                else:
                    set_last = next_backing.setter(target)
                    chunk = next_backing.getter(target)
                chunk = basic_v.backing_from_base(chunk, i % elems_per_chunk)
                next_backing = set_last(chunk)
            else:
                raise Exception("cannot append a packed element that is not a basic type")
        else:
            target: Gindex = to_gindex(i, self.__class__.tree_depth())
            set_last = self.get_backing().setter(target, expand=True)
            next_backing = set_last(v.get_backing())

        set_length = next_backing.rebind_right
        new_length = uint256(ll + 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def pop(self):
        ll = self.length()
        if ll == 0:
            raise Exception("list is empty, cannot pop")
        i = ll - 1
        target: Gindex
        can_summarize: bool
        if self.__class__.is_packed():
            next_backing = self.get_backing()
            elem_type: Type[View] = self.__class__.element_cls()
            if isinstance(elem_type, BasicTypeDef):
                elems_per_chunk = 32 // elem_type.type_byte_length()
                chunk_i = i // elems_per_chunk
                target = to_gindex(chunk_i, self.__class__.tree_depth())
                if i % elems_per_chunk == 0:
                    chunk = zero_node(0)
                else:
                    chunk = next_backing.getter(target)
                set_last = next_backing.setter(target)
                chunk = cast(BasicView, elem_type.default(None)).backing_from_base(chunk, i % elems_per_chunk)
                next_backing = set_last(chunk)

                can_summarize = (target & 1) == 0 and i % elems_per_chunk == 0
            else:
                raise Exception("cannot pop a packed element that is not a basic type")
        else:
            target = to_gindex(i, self.__class__.tree_depth())
            set_last = self.get_backing().setter(target)
            next_backing = set_last(zero_node(0))
            can_summarize = (target & 1) == 0

        # if possible, summarize
        if can_summarize:
            # summarize to the highest node possible.
            # I.e. the resulting target must be a right-hand, unless it's the only content node.
            while (target & 1) == 0 and target != 0b10:
                target >>= 1
            summary_fn = next_backing.summarize_into(target)
            next_backing = summary_fn()

        set_length = next_backing.rebind_right
        new_length = uint256(ll - 1).get_backing()
        next_backing = set_length(new_length)
        self.set_backing(next_backing)

    def get(self, i: int) -> View:
        if i < 0 or i >= self.length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i < 0 or i >= self.length():
            raise IndexError
        super().set(i, v)

    def __repr__(self):
        return self._repr_sequence()

    @classmethod
    def type_repr(cls) -> str:
        return f"List[{cls.element_cls().__name__}, {cls.limit()}]"

    @classmethod
    def is_packed(cls) -> bool:
        raise NotImplementedError

    @classmethod
    def contents_depth(cls) -> int:
        raise NotImplementedError

    @classmethod
    def tree_depth(cls) -> int:
        return cls.contents_depth() + 1  # 1 extra for length mix-in

    @classmethod
    def item_elem_cls(cls, i: int) -> Type[V]:
        return cls.element_cls()

    @classmethod
    def limit(cls) -> int:
        raise NotImplementedError

    @classmethod
    def is_valid_count(cls, count: int) -> bool:
        return 0 <= count <= cls.limit()

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key >= cls.limit():
            raise KeyError
        return super().navigate_type(key)

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        if key >= cls.limit():
            raise KeyError
        return super().key_to_static_gindex(key)

    @classmethod
    def default_node(cls) -> Node:
        return PairNode(zero_node(cls.contents_depth()), zero_node(0))  # mix-in 0 as list length

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return False

    @classmethod
    def min_byte_length(cls) -> int:
        return 0

    @classmethod
    def max_byte_length(cls) -> int:
        elem_cls = cls.element_cls()
        bytes_per_elem = elem_cls.max_byte_length()
        if not elem_cls.is_fixed_byte_length():
            bytes_per_elem += OFFSET_BYTE_LENGTH
        return bytes_per_elem * cls.limit()

    def to_obj(self) -> ObjType:
        return list(el.to_obj() for el in self.readonly_iter())


class Vector(MonoSubtreeView):
    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init Vector")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        elem_cls = cls.element_cls()
        vals = list(args)
        if len(vals) == 1:
            val = vals[0]
            if isinstance(val, (GeneratorType, list, tuple)):
                vals = list(val)
            if issubclass(elem_cls, uint8):
                if isinstance(val, bytes):
                    vals = list(val)
                if isinstance(val, str):
                    if val[:2] == '0x':
                        val = val[2:]
                    vals = list(bytes.fromhex(val))
        if len(vals) > 0:
            vector_length = cls.vector_length()
            if len(vals) != vector_length:
                raise Exception(f"invalid inputs length: {len(vals)}, vector length is: {vector_length}")
            input_views = []
            for el in vals:
                if isinstance(el, View):
                    input_views.append(el)
                else:
                    input_views.append(elem_cls.coerce_view(el))
            input_nodes = cls.views_into_chunks(input_views)
            backing = subtree_fill_to_contents(input_nodes, cls.tree_depth())
        return super().__new__(cls, backing=backing, hook=hook, **kwargs)

    def __class_getitem__(cls, params) -> Type["Vector"]:
        (element_view_cls, length) = params
        if length <= 0:
            raise Exception(f"Invalid vector length: {length}")

        tree_depth = 0
        packed = False
        if isinstance(element_view_cls, BasicTypeDef):
            elems_per_chunk = 32 // element_view_cls.type_byte_length()
            tree_depth = get_depth((length + elems_per_chunk - 1) // elems_per_chunk)
            packed = True
        else:
            tree_depth = get_depth(length)

        class SpecialVectorView(Vector):
            @classmethod
            def is_packed(cls) -> bool:
                return packed

            @classmethod
            def tree_depth(cls) -> int:
                return tree_depth

            @classmethod
            def element_cls(cls) -> Type[View]:
                return element_view_cls

            @classmethod
            def vector_length(cls) -> int:
                return length

        # for fixed-size vectors, pre-compute the size.
        if element_view_cls.is_fixed_byte_length():
            byte_length = element_view_cls.type_byte_length() * length

            class FixedSpecialVectorView(SpecialVectorView):
                @classmethod
                def type_byte_length(cls) -> int:
                    return byte_length

                @classmethod
                def min_byte_length(cls) -> int:
                    return byte_length

                @classmethod
                def max_byte_length(cls) -> int:
                    return byte_length

            SpecialVectorView = FixedSpecialVectorView

        SpecialVectorView.__name__ = SpecialVectorView.type_repr()
        return SpecialVectorView

    def get(self, i: int) -> View:
        if i < 0 or i >= self.__class__.vector_length():
            raise IndexError
        return super().get(i)

    def set(self, i: int, v: View) -> None:
        if i < 0 or i >= self.__class__.vector_length():
            raise IndexError
        super().set(i, v)

    def length(self) -> int:
        return self.__class__.vector_length()

    def value_byte_length(self) -> int:
        if self.__class__.is_fixed_byte_length():
            return self.__class__.type_byte_length()
        else:
            return sum(OFFSET_BYTE_LENGTH + cast(View, el).value_byte_length() for el in iter(self))

    def __repr__(self):
        return self._repr_sequence()

    @classmethod
    def type_repr(cls) -> str:
        return f"Vector[{cls.element_cls().__name__}, {cls.vector_length()}]"

    @classmethod
    def vector_length(cls) -> int:
        raise NotImplementedError

    @classmethod
    def is_valid_count(cls, count: int) -> bool:
        return count == cls.vector_length()

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        if key >= cls.vector_length():
            raise KeyError
        return super().navigate_type(key)

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        if key >= cls.vector_length():
            raise KeyError
        return super().key_to_static_gindex(key)

    @classmethod
    def default_node(cls) -> Node:
        elem_type: Type[View] = cls.element_cls()
        length = cls.to_chunk_length(cls.vector_length())
        if cls.is_packed():
            elem = zero_node(0)
        else:
            elem = elem_type.default_node()
        return subtree_fill_to_length(elem, cls.tree_depth(), length)

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return cls.element_cls().is_fixed_byte_length()  # only if the element type is fixed byte length.

    @classmethod
    def min_byte_length(cls) -> int:
        elem_cls = cls.element_cls()
        bytes_per_elem = elem_cls.min_byte_length()
        if not elem_cls.is_fixed_byte_length():
            bytes_per_elem += OFFSET_BYTE_LENGTH
        return bytes_per_elem * cls.vector_length()

    @classmethod
    def max_byte_length(cls) -> int:
        elem_cls = cls.element_cls()
        bytes_per_elem = elem_cls.max_byte_length()
        if not elem_cls.is_fixed_byte_length():
            bytes_per_elem += OFFSET_BYTE_LENGTH
        return bytes_per_elem * cls.vector_length()

    def to_obj(self) -> ObjType:
        return tuple(el.to_obj() for el in self.readonly_iter())


Fields = Dict[str, Type[View]]


class FieldOffset(NamedTuple):
    key: str
    typ: Type[View]
    offset: int


@runtime_checkable
class _ContainerLike(Protocol):
    @classmethod
    def fields(cls) -> Fields:
        ...


class Container(ComplexView):
    # Container types should declare fields through class annotations.
    # If none are specified, it will fall back on this (to avoid annotations of super classes),
    # and error on construction, since empty container types are invalid.
    _empty_annotations: bool
    _field_indices: Dict[str, int]

    def __new__(cls, *args, backing: Optional[Node] = None, hook: Optional[ViewHook] = None, **kwargs):
        if backing is not None:
            if len(args) != 0:
                raise Exception("cannot have both a backing and elements to init List")
            return super().__new__(cls, backing=backing, hook=hook, **kwargs)

        input_nodes = []
        for fkey, ftyp in cls.fields().items():
            fnode: Node
            if fkey in kwargs:
                finput = kwargs.pop(fkey)
                if isinstance(finput, View):
                    fnode = finput.get_backing()
                else:
                    fnode = ftyp.coerce_view(finput).get_backing()
            else:
                fnode = ftyp.default_node()
            input_nodes.append(fnode)
        # check if any keys are remaining to catch unrecognized keys
        if len(kwargs) > 0:
            raise AttributeError(f'The field names [{"".join(kwargs.keys())}] are not defined in {cls}')
        backing = subtree_fill_to_contents(input_nodes, cls.tree_depth())
        out = super().__new__(cls, backing=backing, hook=hook)
        return out

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        cls._field_indices = {fkey: i for i, fkey in enumerate(cls.__annotations__.keys()) if fkey[0] != '_'}
        if len(cls._field_indices) == 0:
            raise Exception(f"Container {cls.__name__} must have at least one field!")

    @classmethod
    def coerce_view(cls: Type[V], v: Any) -> V:
        return cls({fkey: getattr(v, fkey) for fkey in cls.fields().keys()})

    @classmethod
    def fields(cls) -> Fields:
        return cls.__annotations__

    @classmethod
    def is_fixed_byte_length(cls) -> bool:
        return all(f.is_fixed_byte_length() for f in cls.fields().values())

    @classmethod
    def type_byte_length(cls) -> int:
        if cls.is_fixed_byte_length():
            return cls.min_byte_length()
        else:
            raise Exception("dynamic length container does not have a fixed byte length")

    @classmethod
    def min_byte_length(cls) -> int:
        total = 0
        for ftyp in cls.fields().values():
            if not ftyp.is_fixed_byte_length():
                total += OFFSET_BYTE_LENGTH
            total += ftyp.min_byte_length()
        return total

    @classmethod
    def max_byte_length(cls) -> int:
        total = 0
        for ftyp in cls.fields().values():
            if not ftyp.is_fixed_byte_length():
                total += OFFSET_BYTE_LENGTH
            total += ftyp.max_byte_length()
        return total

    @classmethod
    def is_packed(cls) -> bool:
        return False

    @classmethod
    def tree_depth(cls) -> int:
        return get_depth(len(cls.fields()))

    @classmethod
    def item_elem_cls(cls, i: int) -> Type[View]:
        return list(cls.fields().values())[i]

    @classmethod
    def default_node(cls) -> Node:
        return subtree_fill_to_contents([field.default_node() for field in cls.fields().values()], cls.tree_depth())

    def value_byte_length(self) -> int:
        if self.__class__.is_fixed_byte_length():
            return self.__class__.type_byte_length()
        else:
            total = 0
            fields = self.fields()
            for fkey, ftyp in fields.items():
                if ftyp.is_fixed_byte_length():
                    total += ftyp.type_byte_length()
                else:
                    total += OFFSET_BYTE_LENGTH
                    total += cast(View, getattr(self, fkey)).value_byte_length()
            return total

    def __getattr__(self, item):
        if item[0] == '_':
            return super().__getattribute__(item)
        else:
            try:
                i = self.__class__._field_indices[item]
            except KeyError:
                raise AttributeError(f"unknown attribute {item}")
            return super().get(i)

    def __setattr__(self, key, value):
        if key[0] == '_':
            super().__setattr__(key, value)
        else:
            try:
                i = self.__class__._field_indices[key]
            except KeyError:
                raise AttributeError(f"unknown attribute {key}")
            super().set(i, value)

    def _get_field_val_repr(self, fkey: str, ftype: Type[View]) -> str:
        field_start = '  ' + fkey + ': ' + ftype.__name__ + ' = '
        try:
            field_repr = repr(getattr(self, fkey))
            if '\n' in field_repr:  # if multiline, indent it, but starting from the value.
                i = field_repr.index('\n')
                field_repr = field_repr[:i+1] + indent(field_repr[i+1:], ' ' * len(field_start))
            return field_start + field_repr
        except NavigationError:
            return f"{field_start} *omitted from partial*"

    def __repr__(self):
        return f"{self.__class__.__name__}(Container)\n" + '\n'.join(
            indent(self._get_field_val_repr(fkey, ftype), '  ')
            for fkey, ftype in self.__class__.fields().items())

    @classmethod
    def type_repr(cls) -> str:
        return f"{cls.__name__}(Container)\n" + '\n'.join(
            ('  ' + fkey + ': ' + ftype.__name__) for fkey, ftype in cls.fields().items())

    def __iter__(self):
        tree_depth = self.tree_depth()
        backing = self.get_backing()
        return ContainerElemIter(backing, tree_depth, list(self.__class__.fields().values()))

    @classmethod
    def decode_bytes(cls: Type[V], bytez: bytes) -> V:
        stream = io.BytesIO()
        stream.write(bytez)
        stream.seek(0)
        return cls.deserialize(stream, len(bytez))

    @classmethod
    def deserialize(cls: Type[V], stream: BinaryIO, scope: int) -> V:
        fields = cls.fields()
        field_values: Dict[str, View]
        if cls.is_fixed_byte_length():
            field_values = {fkey: ftyp.deserialize(stream, ftyp.type_byte_length()) for fkey, ftyp in fields.items()}
        else:
            field_values = {}
            dyn_fields: PyList[FieldOffset] = []
            fixed_size = 0
            for fkey, ftyp in fields.items():
                if ftyp.is_fixed_byte_length():
                    fsize = ftyp.type_byte_length()
                    field_values[fkey] = ftyp.deserialize(stream, fsize)
                    fixed_size += fsize
                else:
                    dyn_fields.append(FieldOffset(key=fkey, typ=ftyp, offset=int(decode_offset(stream))))
                    fixed_size += OFFSET_BYTE_LENGTH
            if len(dyn_fields) > 0:
                if dyn_fields[0].offset < fixed_size:
                    raise Exception(f"first offset is smaller than expected fixed size")
                for i, (fkey, ftyp, foffset) in enumerate(dyn_fields):
                    next_offset = dyn_fields[i + 1].offset if i + 1 < len(dyn_fields) else scope
                    if foffset > next_offset:
                        raise Exception(f"offset {i} is invalid: {foffset} larger than next offset {next_offset}")
                    fsize = next_offset - foffset
                    f_min_size, f_max_size = ftyp.min_byte_length(), ftyp.max_byte_length()
                    if not (f_min_size <= fsize <= f_max_size):
                        raise Exception(f"offset {i} is invalid, size out of bounds: {foffset}, next {next_offset},"
                                        f" implied size: {fsize}, size bounds: [{f_min_size}, {f_max_size}]")
                    field_values[fkey] = ftyp.deserialize(stream, fsize)
        return cls(**field_values)

    def serialize(self, stream: BinaryIO) -> int:
        fields = self.__class__.fields()
        is_fixed_size = self.is_fixed_byte_length()
        temp_dyn_stream = None if is_fixed_size else io.BytesIO()
        written = sum(map((lambda x: x.type_byte_length() if x.is_fixed_byte_length() else OFFSET_BYTE_LENGTH),
                          fields.values()))
        for fkey, ftyp in fields.items():
            v: View = getattr(self, fkey)
            if ftyp.is_fixed_byte_length():
                v.serialize(stream)
            else:
                encode_offset(stream, written)
                written += v.serialize(temp_dyn_stream)
        if not is_fixed_size:
            temp_dyn_stream.seek(0)
            stream.write(temp_dyn_stream.read(written))
        return written

    @classmethod
    def from_obj(cls: Type[V], obj: ObjType) -> V:
        if not isinstance(obj, dict):
            raise ObjParseException(f"obj '{obj}' is not a dict")
        fields = cls.fields()
        for k in obj.keys():
            if k not in fields:
                raise ObjParseException(f"obj '{obj}' has unknown key {k}")
        return cls(**{k: fields[k].from_obj(v) for k, v in obj.items()})

    def to_obj(self) -> ObjType:
        return {f_k: f_v.to_obj() for f_k, f_v in zip(self.__class__.fields().keys(), self.__iter__())}

    @classmethod
    def key_to_static_gindex(cls, key: Any) -> Gindex:
        fields = cls.fields()
        try:
            field_index = list(fields.keys()).index(key)
        except ValueError:  # list.index raises ValueError if the element (a key here) is missing
            raise KeyError
        return to_gindex(field_index, cls.tree_depth())

    @classmethod
    def navigate_type(cls, key: Any) -> Type[View]:
        return cls.fields()[key]

    def navigate_view(self, key: Any) -> View:
        return self.__getattr__(key)
