from ..merkle_minimal import hash, next_power_of_two

from .ssz_typing import (
    Container, Elements,
    List, Bytes32, uint64, BasicValue, SSZValue, SSZType, coerce_type_maybe
)
from .ssz_impl import (
    chunkify,
    deserialize_basic,
    is_bottom_layer_kind,
    item_length,
    chunk_count,
    pack,
    serialize_basic,
)

from typing import Union, Type, Dict


ComplexType = Union[Type[Container], Type[Elements]]

ZERO_CHUNK = b'\x00' * 32


def is_generalized_index_child(c, a):
    return False if c < a else True if c == a else is_generalized_index_child(c // 2, a)


def empty_sisters(starting_position, list_size, max_list_size):
    """
    Returns the sister nodes representing empty data needed to complete a Merkle
    partial of a list from [starting_position: starting_position + list_size]
    with theoretical max length max_list_size. For example empty_sisters(13, 1, 4)
    would return the correct hashes at the g-indices in square brackets in the
    sub-tree of 13:
           13
      26      [27]
    52 [53]  54  55
    """
    at, skip, end = list_size, 1, next_power_of_two(max_list_size)
    value = ZERO_CHUNK
    o = {}
    while at < end:
        while (at+end) % (skip * 2) == 0:
            skip *= 2
            value = hash(value + value)
        o[(starting_position + at) // skip] = value
        at += skip
    return o


def ssz_leaves(obj: SSZValue, root=1):
    """
    Converts an object into a {generalized_index: chunk} map. Leaves only; does not fill
    intermediate chunks or compute the root.
    """
    typ = obj.type()
    if isinstance(obj, (List, Bytes)):
        o = {root * 2 + 1: len(obj).to_bytes(32, 'little')}
        base = root * 2
    else:
        o = {}
        base = root
    starting_index = base * next_power_of_two(chunk_count(typ))
    if is_bottom_layer_kind(typ):
        data = chunkify(serialize_basic(obj) if isinstance(obj, BasicValue) else pack(obj))
        return {
            **o,
            **{starting_index + i: data[i] for i in range(len(data))},
            **empty_sisters(starting_index, len(data), chunk_count(typ))
        }
    else:
        for i, elem in enumerate(obj):
            o = {**o, **ssz_leaves(elem, root=starting_index + i)}
        return {**o, **empty_sisters(starting_index, len(obj), chunk_count(typ))}


def fill(objects):
    """
    Given a {generalized_index: chunk} map containing only leaves, fills intermediate
    chunks as far as possible.
    """
    objects = {k: v for k, v in objects.items()}
    keys = sorted(objects.keys())[::-1]
    pos = 0
    while pos < len(keys):
        k = keys[pos]
        if k in objects and k ^ 1 in objects and k // 2 not in objects:
            objects[k // 2] = hash(objects[k & - 2] + objects[k | 1])
            keys.append(k // 2)
        pos += 1
    return objects


def ssz_full(obj):
    return fill(ssz_leaves(obj))


def get_elem_type(typ: ComplexType, key: Union[str, int]):
    """
    Returns the type of the element of an object of the given type with the given index
    or member variable name (eg. `7` for `x[7]`, `"foo"` for `x.foo`)
    """
    return typ.get_fields()[key] if issubclass(typ, Container) else typ.elem_type


def get_generalized_index(typ: SSZPartial, root, path):
    """
    Converts a path (eg. `[7, "foo", 3]` for `x[7].foo[3]`, `[12, "bar", "__len__"]` for
    `len(x[12].bar)`) into the generalized index representing its position in the Merkle tree.
    """
    for p in path:
        assert not issubclass(typ, BasicValue)  # If we descend to a basic type, the path cannot continue further
        if p == '__len__':
            typ, root = uint64, root * 2 + 1 if issubclass(typ, list) else None
        else:
            pos, _, _ = typ.get_item_position(p)
            root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(chunk_count(typ)) + pos
            typ = get_elem_type(typ, p)
    return root


def extract_value_at_path(chunks, typ: SSZPartial, path):
    """
    Provides the value of the element in the object represented by the given encoded SSZ partial at
    the given path. Returns a KeyError if that path is not covered by this SSZ partial.
    """
    root = 1
    for p in path:
        if p == '__len__':
            return deserialize_basic(chunks[root * 2 + 1][:8], uint64)
        if typ.can_grow():
            assert 0 <= p < deserialize_basic(chunks[root * 2 + 1][:8], uint64)
        pos, start, end = typ.get_item_position(p)
        root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(chunk_count(typ)) + pos
        typ = get_elem_type(typ, p)
    return deserialize_basic(chunks[root][start: end], typ)


def get_generalized_index_correspondence(typ: SSZType, root=1, path=None):
    """
    Prints the path corresponding to every leaf-level generalized index in an SSZ object
    """
    path = path or []
    if issubclass(typ, BasicValue):
        return {root: path}
    if issubclass(typ, Elements):
        fields = list(range(typ.length))
    elif issubclass(typ, Container):
        fields = list(typ.get_fields().keys())
    else:
        raise Exception("unknown type")
    o = {}
    for f in fields:
        o = {
            **o,
            **get_generalized_index_correspondence(
                get_elem_type(typ, f),
                get_generalized_index(typ, root, [f]),
                path + [f]
            )
        }
    o[root] = path
    if issubclass(typ, Elements) and typ.can_grow():  # add node for mix-in
        o[root * 2 + 1] = path + ['__len__']
    return o


def get_branch_indices(tree_index):
    """
    Get the generalized indices of the sister chunks along the path from the chunk with the
    given tree index to the root.
    """
    o = [tree_index ^ 1]
    while o[-1] > 1:
        o.append((o[-1] // 2) ^ 1)
    return o[:-1]


def expand_indices(indices):
    """
    Get the generalized indices of all chunks in the tree needed to prove the chunks with the given
    generalized indices.
    """
    branches = set()
    for index in indices:
        branches = branches.union(set(get_branch_indices(index) + [index]))
    return sorted(list([x for x in branches if x * 2 not in branches or x * 2 + 1 not in branches]))[::-1]


class OutOfRangeException(Exception):
    pass


class SSZPartial:
    _objects: Dict[int, bytes]
    _root: int

    def compile(self, objects, root):
        self._objects = objects
        self._root = root

    def clear_subtree(self, tree_index):
        for k in list(self._objects.keys()):
            if is_generalized_index_child(k, tree_index):
                del self._objects[k]

    @classmethod
    def get_item_position(cls, index):
        """
        Returns three variables:
         1. the index of the chunk in which the given element of the item is represented
         2. the starting byte position
         3. the ending byte position. For example for a 6-item list of uint64 values,
             index=2 will return (0, 16, 24), index=5 will return (1, 8, 16)
        """
        raise Exception("Not implemented, subclass me")

    def __len__(self):
        raise Exception("Not implemented, subclass me")

    def __iter__(self):
        return (self.getter(i) for i in range(len(self)))

    def getter(self, index):
        raise Exception("Not implemented, subclass me")

    def setter(self, index, value, renew=True):
        raise Exception("Not implemented, subclass me")

    def renew_branch(self, tree_index):
        while tree_index > 1:
            self._objects[tree_index // 2] = hash(self._objects[tree_index & -2] + self._objects[tree_index | 1])
            tree_index //= 2

    def minimal_indices(self):
        raise Exception("Not implemented, subclass me")

    def hash_tree_root(self):
        o = {**self._objects}
        keys = sorted(o.keys())[::-1]
        pos = 0
        while pos < len(keys):
            k = keys[pos]
            if k in o and k ^ 1 in o and k // 2 not in o:
                o[k // 2] = hash(o[k & - 2] + o[k | 1])
                keys.append(k // 2)
            pos += 1
        return o[self._root]

    def __str__(self):
        return str(self.full_value())

    def __eq__(self, other):
        if isinstance(other, SSZPartial):
            return self.full_value() == other.full_value()
        else:
            return self.full_value() == other

    def encode(self):
        """
        Convert to an EncodedPartial.
        """
        indices = self.minimal_indices()
        chunks = [self._objects[o] for o in expand_indices(indices)]
        return EncodedPartial(indices=indices, chunks=chunks)

    def full_value(self):
        raise Exception("Not implemented, subclass me")


class ElementsPartial(SSZPartial, Elements):

    def full_value(self):
        typ = self.type()
        return typ(self.getter(i).full_value() for i in range(len(self)))

    @classmethod
    def get_item_position(cls, index):
        start = index * item_length(cls.elem_type)
        return start // 32, start % 32, start % 32 + item_length(cls.elem_type)

    def base(self):
        return self._root * 2 if self.type().can_grow() else self._root

    def append_or_pop(self, appending, value):
        typ = self.type()
        assert typ.can_grow()

        old_length = len(self)
        new_length = old_length + (1 if appending else -1)
        if new_length < 0:
            raise Exception("Can't pop from empty list/bytes!")
        elif new_length > typ.length:
            raise Exception("Can't append to full list/bytes!")

        elem_type = typ.elem_type
        self._objects[self._root * 2 + 1] = new_length.to_bytes(32, 'little')
        old_chunk_count = (old_length * item_length(elem_type) + 31) // 32
        new_chunk_count = (new_length * item_length(elem_type) + 31) // 32

        start_pos = self._root * 2 * next_power_of_two(chunk_count(typ))
        if new_chunk_count != old_chunk_count:
            for k, v in empty_sisters(start_pos, old_chunk_count, chunk_count(typ)).items():
                del self._objects[k]
        if not appending:
            if issubclass(elem_type, BasicValue):
                self.setter(old_length - 1, elem_type.default(), renew=False)
            else:
                self.clear_subtree(get_generalized_index(typ, self._root, [old_length - 1]))
        else:
            self.setter(new_length - 1, value, renew=False)

        if new_chunk_count != old_chunk_count:
            for k, v in empty_sisters(start_pos, new_chunk_count, chunk_count(typ)).items():
                self.clear_subtree(k)
                self._objects[k] = v

        self.renew_branch(get_generalized_index(typ, self._root, [new_length - 1]))

    def append(self, value):
        return self.append_or_pop(True, value)

    def pop(self):
        return self.append_or_pop(False, None)

    def __len__(self):
        if self.type().can_grow():  # derive length from mix-in if it has a dynamic length
            if self._root * 2 + 1 not in self._objects:
                raise OutOfRangeException("Do not have required data: {}".format(self._root * 2 + 1))
            return int.from_bytes(self._objects[self._root * 2 + 1], 'little')
        else:
            return super().__len__()


class BasicElementsPartial(ElementsPartial, Elements):

    def minimal_indices(self):
        if self._root * 2 + 1 not in self._objects:
            return []
        o = list(range(
            get_generalized_index(self.type(), self._root, [0]),
            get_generalized_index(self.type(), self._root, [len(self) - 1]) + 1
        ))
        return [x for x in o if x in self._objects]

    def setter(self, index, value, renew=True):
        typ = self.type()
        value = coerce_type_maybe(value, typ.elem_type, strict=True)

        pos, start, end = typ.get_item_position(index)
        tree_index = self.base() * next_power_of_two(chunk_count(typ)) + pos
        if tree_index not in self._objects:
            raise OutOfRangeException("Do not have required data")
        else:
            chunk = self._objects[tree_index]
            self._objects[tree_index] = chunk[:start] + serialize_basic(value) + chunk[end:]
            assert len(self._objects[tree_index]) == 32

        if renew:
            self.renew_branch(tree_index)

    def getter(self, index):
        base = self._root
        typ = self.type()

        if isinstance(self, typ.can_grow()):
            base *= 2  # add mix in depth

        pos, start, end = typ.get_item_position(index)
        tree_index = base * next_power_of_two(chunk_count(typ)) + pos
        if tree_index not in self._objects:
            raise OutOfRangeException("Do not have required data")
        else:
            return deserialize_basic(
                self._objects[tree_index][start:end],
                typ.elem_type
            )


class ComplexElementsPartial(ElementsPartial):

    def minimal_indices(self):
        return sum([self.getter(i).minimal_indices() for i in range(len(self))], [])

    def setter(self, index, value, renew=True):
        typ = self.type()
        tree_index = get_generalized_index(typ, self._root, [index])
        self.clear_subtree(tree_index)
        for k, v in fill(ssz_leaves(value, tree_index)).items():
            self._objects[k] = v
        if renew:
            self.renew_branch(tree_index)

    def getter(self, index):
        typ = self.type()
        return ssz_partial(
            typ.elem_type,
            self._objects,
            get_generalized_index(typ, self._root, [index])
        )


class ContainerPartial(SSZPartial, Container):

    @classmethod
    def get_elem_type(cls, key) -> SSZType:
        return cls.get_fields()[key]

    @classmethod
    def get_item_position(cls, index):
        return list(cls.get_fields().keys()).index(index), 0, item_length(cls.get_elem_type(index))

    def getter(self, index):
        return ssz_partial(
            get_elem_type(self.type(), index),
            self._objects,
            get_generalized_index(self.type(), self._root, [index])
        )

    def setter(self, index, value, renew=True):
        base = self._root
        typ = self.type()
        elem_type = self.get_elem_type(index)
        value = coerce_type_maybe(value, elem_type, strict=True)
        if issubclass(elem_type, BasicValue):
            pos, start, end = typ.get_item_position(index)
            tree_index = base * next_power_of_two(chunk_count(typ)) + pos
            if tree_index not in self._objects:
                raise OutOfRangeException("Do not have required data")
            else:
                chunk = self._objects[tree_index]
                self._objects[tree_index] = chunk[:start] + serialize_basic(value) + chunk[end:]
                assert len(self._objects[tree_index]) == 32
        else:
            tree_index = get_generalized_index(typ, self._root, [index])
            self.clear_subtree(tree_index)
            for k, v in fill(ssz_leaves(value, tree_index)).items():
                self._objects[k] = v
        if renew:
            self.renew_branch(tree_index)

    def access_partial(self, path):
        typ = self.type()
        gindex = get_generalized_index(typ, self._root, path)
        branch_keys = get_branch_indices(gindex)
        item_keys = [k for k in self._objects if is_generalized_index_child(k, gindex)]
        return ssz_partial(typ,
                           {i: self._objects[i] for i in self._objects if i in branch_keys + item_keys},
                           self._root)

    def full_value(self):
        typ = self.type()
        return typ(**{field: self.getter(field).full_value() for field in typ.get_fields().keys()})

    def minimal_indices(self):
        o = []
        for field, elem_type in self.get_fields().items():
            if issubclass(elem_type, BasicValue):
                gindex = get_generalized_index(self.type(), self._root, [field])
                if gindex in self._objects:
                    o.append(gindex)
            else:
                o.extend(self.getter(field).minimal_indices())
        return o


def ssz_partial(typ: SSZType, objects, root=1):
    """
    A wrapper that creates an SSZ partial class that is also a subclass of the class
    representing the underlying type.
    """
    # todo: construct type that subclasses both SSZPartial and given typ.

    # todo: refactor, move to ContainerPartial, with __getattr__ override
    # if issubclass(typ, Container):
    #     Partial.__annotations__ = typ.__annotations__
    #     for field in typ.get_fields().keys():
    #         setattr(Partial, field, property(
    #             (lambda f: (lambda self: self.getter(f)))(field),
    #             (lambda f: (lambda self, v: self.setter(f, v)))(field)
    #         ))
    # todo instantiate the new type, and fill it with objects + root gen-index
    # o = Partial(typ, objects, root)
    return None


def merge(*args: SSZPartial):
    o = {}
    for arg in args:
        o = {**o, **arg._objects}
    return ssz_partial(args[0].ssz_type(), fill(o))


class EncodedPartial(Container):
    indices: List[uint64, 2 ** 32]
    chunks: List[Bytes32, 2 ** 32]

    def to_ssz(self, typ):
        """
        Convert to an SSZ partial representing the given type.
        """
        expanded_indices = expand_indices(self.indices)
        o = ssz_partial(typ, fill({e: bytes(c) for e, c in zip(expanded_indices, self.chunks)}))
        for k, v in o._objects.items():
            if k > 1:
                assert hash(o._objects[k & -2] + o._objects[k | 1]) == o._objects[k // 2]
        return o
