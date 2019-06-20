from ..merkle_minimal import hash, next_power_of_two

from .ssz_typing import (
    Container, List, Vector, Bytes, BytesN, uint64, byte, BasicValue, SSZValue, coerce_type_maybe
)
from .ssz_impl import (
    chunkify,
    deserialize_basic,
    is_bottom_layer_kind,
    item_length,
    get_chunk_count,
    pack,
    serialize_basic,
)


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
    if is_bottom_layer_kind(typ):
        starting_index = base * next_power_of_two(get_chunk_count(typ))
        data = chunkify(serialize_basic(obj) if isinstance(obj, BasicValue) else pack(obj))
        return {
            **o,
            **{starting_index + i: data[i] for i in range(len(data))},
            **empty_sisters(starting_index, len(data), get_chunk_count(typ))
        }
    else:
        for i, elem in enumerate(obj):
            o = {**o, **ssz_leaves(elem, root=starting_index + i)}
        return {**o, **empty_sisters(starting_index, len(obj), get_chunk_count(typ))}


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


def get_item_position(typ, index):
    """
    Returns three variables: (i) the index of the chunk in which the given element of the item is
    represented, (ii) the starting byte position, (iii) the ending byte position. For example for
    a 6-item list of uint64 values, index=2 will return (0, 16, 24), index=5 will return (1, 8, 16)
    """
    if issubclass(typ, (List, Bytes)) or issubclass(typ, (Vector, BytesN)):
        start = index * item_length(typ.elem_type)
        return start // 32, start % 32, start % 32 + item_length(typ.elem_type)
    elif issubclass(typ, Container):
        return list(typ.get_fields().keys()).index(index), 0, item_length(get_elem_type(typ, index))
    else:
        raise Exception("Only lists/vectors/containers supported")


def get_elem_type(typ, index):
    """
    Returns the type of the element of an object of the given type with the given index
    or member variable name (eg. `7` for `x[7]`, `"foo"` for `x.foo`)
    """
    return typ.get_fields()[index] if issubclass(typ, Container) else typ.elem_type


def get_generalized_index(typ, root, path):
    """
    Converts a path (eg. `[7, "foo", 3]` for `x[7].foo[3]`, `[12, "bar", "__len__"]` for
    `len(x[12].bar)`) into the generalized index representing its position in the Merkle tree.
    """
    for p in path:
        assert not issubclass(typ, BasicValue)  # If we descend to a basic type, the path cannot continue further
        if p == '__len__':
            typ, root = uint64, root * 2 + 1 if issubclass(typ, list) else None
        else:
            pos, _, _ = get_item_position(typ, p)
            root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(get_chunk_count(typ)) + pos
            typ = get_elem_type(typ, p)
    return root


def extract_value_at_path(chunks, typ, path):
    """
    Provides the value of the element in the object represented by the given encoded SSZ partial at
    the given path. Returns a KeyError if that path is not covered by this SSZ partial.
    """
    root = 1
    for p in path:
        if p == '__len__':
            return deserialize_basic(chunks[root * 2 + 1][:8], uint64)
        if issubclass(typ, (List, Bytes)):
            assert 0 <= p < deserialize_basic(chunks[root * 2 + 1][:8], uint64)
        pos, start, end = get_item_position(typ, p)
        root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(get_chunk_count(typ)) + pos
        typ = get_elem_type(typ, p)
    return deserialize_basic(chunks[root][start: end], typ)


def get_generalized_index_correspondence(typ, root=1, path=None):
    """
    Prints the path corresponding to every leaf-level generalized index in an SSZ object
    """
    path = path or []
    if issubclass(typ, BasicValue):
        return {root: path}
    if issubclass(typ, (List, Vector, Bytes, BytesN)):
        fields = list(range(typ.length))
    else:
        fields = list(typ.get_fields().keys())
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
    if issubclass(typ, (List, Bytes)):
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


def merge(*args):
    o = {}
    for arg in args:
        o = {**o, **arg.objects}
    return ssz_partial(args[0].typ, fill(o))


class OutOfRangeException(Exception):
    pass


class SSZPartial():
    def __init__(self, typ, objects, root=1):
        assert not issubclass(typ, BasicValue)
        self.objects = objects
        self.typ = typ
        self.root = root

    def getter(self, index):
        base = self.root * 2 if issubclass(self.typ, (List, Bytes)) else self.root
        if issubclass(get_elem_type(self.typ, index), BasicValue):
            pos, start, end = get_item_position(self.typ, index)
            tree_index = base * next_power_of_two(get_chunk_count(self.typ)) + pos
            if tree_index not in self.objects:
                raise OutOfRangeException("Do not have required data")
            else:
                return deserialize_basic(
                    self.objects[tree_index][start:end],
                    self.typ if issubclass(self.typ, BasicValue) else get_elem_type(self.typ, index)
                )
        else:
            return ssz_partial(
                get_elem_type(self.typ, index),
                self.objects,
                get_generalized_index(self.typ, self.root, [index])
            )

    def clear_subtree(self, tree_index):
        for k in list(self.objects.keys()):
            if is_generalized_index_child(k, tree_index):
                del self.objects[k]

    def renew_branch(self, tree_index):
        while tree_index > 1:
            self.objects[tree_index // 2] = hash(self.objects[tree_index & -2] + self.objects[tree_index | 1])
            tree_index //= 2

    def setter(self, index, value, renew=True):
        base = self.root * 2 if issubclass(self.typ, (List, Bytes)) else self.root
        elem_type = get_elem_type(self.typ, index)
        value = coerce_type_maybe(value, elem_type, strict=True)
        if issubclass(elem_type, BasicValue):
            pos, start, end = get_item_position(self.typ, index)
            tree_index = base * next_power_of_two(get_chunk_count(self.typ)) + pos
            if tree_index not in self.objects:
                raise OutOfRangeException("Do not have required data")
            else:
                chunk = self.objects[tree_index]
                self.objects[tree_index] = chunk[:start] + serialize_basic(value) + chunk[end:]
                assert len(self.objects[tree_index]) == 32
        else:
            tree_index = get_generalized_index(self.typ, self.root, [index])
            self.clear_subtree(tree_index)
            for k, v in fill(ssz_leaves(value, tree_index)).items():
                self.objects[k] = v
        if renew:
            self.renew_branch(tree_index)

    def append_or_pop(self, appending, value):
        assert issubclass(self.typ, (List, Bytes))
        old_length = len(self)
        new_length = old_length + (1 if appending else -1)
        if new_length < 0:
            raise Exception("Can't pop from empty list/bytes!")
        elif new_length > self.typ.length:
            raise Exception("Can't append to full list/bytes!")
        elem_type = get_elem_type(self.typ, None)
        self.objects[self.root * 2 + 1] = new_length.to_bytes(32, 'little')
        old_chunk_count = (old_length * item_length(elem_type) + 31) // 32
        new_chunk_count = (new_length * item_length(elem_type) + 31) // 32
        start_pos = self.root * 2 * next_power_of_two(get_chunk_count(self.typ))
        if new_chunk_count != old_chunk_count:
            for k, v in empty_sisters(start_pos, old_chunk_count, get_chunk_count(self.typ)).items():
                del self.objects[k]
        if not appending:
            if issubclass(elem_type, BasicValue):
                self.setter(old_length - 1, elem_type.default(), renew=False)
            else:
                self.clear_subtree(get_generalized_index(self.typ, self.root, [old_length - 1]))
        else:
            self.setter(new_length - 1, value, renew=False)
        if new_chunk_count != old_chunk_count:
            for k, v in empty_sisters(start_pos, new_chunk_count, get_chunk_count(self.typ)).items():
                self.clear_subtree(k)
                self.objects[k] = v
        self.renew_branch(get_generalized_index(self.typ, self.root, [new_length - 1]))

    def append(self, value):
        return self.append_or_pop(True, value)

    def pop(self):
        return self.append_or_pop(False, None)

    def __setitem__(self, index, value):
        return self.setter(index, value)

    def access_partial(self, path):
        gindex = get_generalized_index(self.typ, self.root, path)
        branch_keys = get_branch_indices(gindex)
        item_keys = [k for k in self.objects if is_generalized_index_child(k, gindex)]
        return ssz_partial(self.typ, {i: self.objects[i] for i in self.objects if i in branch_keys + item_keys},
                           self.root)

    def __getitem__(self, index):
        return self.getter(index)

    def __iter__(self):
        return (self[i] for i in range(len(self)))

    def __len__(self):
        if issubclass(self.typ, (List, Bytes)):
            if self.root * 2 + 1 not in self.objects:
                raise OutOfRangeException("Do not have required data: {}".format(self.root * 2 + 1))
            return int.from_bytes(self.objects[self.root * 2 + 1], 'little')
        elif issubclass(self.typ, (Vector, BytesN)):
            return self.typ.length
        elif issubclass(self.typ, Container):
            return len(self.typ.get_fields())
        else:
            raise Exception("Unsupported type: {}".format(self.typ))

    def full_value(self):
        if issubclass(self.typ, (Bytes, BytesN)):
            return self.typ(bytes([self.getter(i) for i in range(len(self))]))
        elif issubclass(self.typ, (List, Vector)):
            return self.typ(*(self[i] for i in range(len(self))))
        elif issubclass(self.typ, Container):
            def full_value(x):
                return x.full_value() if hasattr(x, 'full_value') else x

            return self.typ(**{field: full_value(self.getter(field)) for field in self.typ.get_fields().keys()})
        elif issubclass(self.typ, BasicValue):
            return self.getter(0)
        else:
            raise Exception("Unsupported type: {}".format(self.typ))

    def hash_tree_root(self):
        o = {**self.objects}
        keys = sorted(o.keys())[::-1]
        pos = 0
        while pos < len(keys):
            k = keys[pos]
            if k in o and k ^ 1 in o and k // 2 not in o:
                o[k // 2] = hash(o[k & - 2] + o[k | 1])
                keys.append(k // 2)
            pos += 1
        return o[self.root]

    def __str__(self):
        return str(self.full_value())

    def __eq__(self, other):
        if isinstance(other, SSZPartial):
            return self.full_value() == other.full_value()
        else:
            return self.full_value() == other

    def minimal_indices(self):
        if is_bottom_layer_kind(self.typ) and issubclass(get_elem_type(self.typ, None), BasicValue):
            if issubclass(self.typ, (List, Bytes)) and self.root * 2 + 1 not in self.objects:
                return []
            o = list(range(
                get_generalized_index(self.typ, self.root, [0]),
                get_generalized_index(self.typ, self.root, [len(self) - 1]) + 1
            ))
            return [x for x in o if x in self.objects]
        elif issubclass(self.typ, Container):
            o = []
            for field, elem_type in self.typ.get_fields().items():
                if issubclass(elem_type, BasicValue):
                    gindex = get_generalized_index(self.typ, self.root, [field])
                    if gindex in self.objects:
                        o.append(gindex)
                else:
                    o.extend(self.getter(field).minimal_indices())
            return o
        else:
            return sum([self.getter(i).minimal_indices() for i in range(len(self))], [])

    def encode(self):
        """
        Convert to an EncodedPartial.
        """
        indices = self.minimal_indices()
        chunks = [self.objects[o] for o in expand_indices(indices)]
        return EncodedPartial(indices=indices, chunks=chunks)


def ssz_partial(typ, objects, root=1):
    """
    A wrapper that creates an SSZ partial class that is also a subclass of the class
    representing the underlying type.
    """
    ssz_type = object if typ == bool else typ

    class Partial(SSZPartial, ssz_type):
        pass

    if issubclass(typ, Container):
        Partial.__annotations__ = typ.__annotations__
        for field in typ.get_fields().keys():
            setattr(Partial, field, property(
                (lambda f: (lambda self: self.getter(f)))(field),
                (lambda f: (lambda self, v: self.setter(f, v)))(field)
            ))
    o = Partial(typ, objects, root)
    return o


class EncodedPartial(Container):
    indices: List[uint64, 2 ** 32]
    chunks: List[BytesN[32], 2 ** 32]

    def to_ssz(self, typ):
        """
        Convert to an SSZ partial representing the given type.
        """
        expanded_indices = expand_indices(self.indices)
        o = ssz_partial(typ, fill({e: bytes(c) for e, c in zip(expanded_indices, self.chunks)}))
        for k, v in o.objects.items():
            if k > 1:
                assert hash(o.objects[k & -2] + o.objects[k | 1]) == o.objects[k // 2]
        return o
