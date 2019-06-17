from ..merkle_minimal import hash, next_power_of_two

from .ssz_typing import (
    get_zero_value, Container, List, Vector, Bytes, BytesN, uint, uint64, infer_input_type
)
from .ssz_impl import (
    chunkify,
    deserialize_basic,
    get_typed_values,
    is_basic_type,
    is_bottom_layer_kind,
    is_list_kind,
    is_vector_kind,
    is_container_type,
    item_length,
    chunk_count,
    pack,
    serialize_basic,
)


ZERO_CHUNK = b'\x00' * 32


def last_power_of_two(x):
    return next_power_of_two(x + 1) // 2


def concat_generalized_indices(x, y):
    return x * last_power_of_two(y) + y - last_power_of_two(y)


def is_generalized_index_child(c, a):
    return False if c < a else True if c == a else is_generalized_index_child(c//2, a)


def rebase(objs, new_root):
    return {concat_generalized_indices(new_root, k): v for k, v in objs.items()}


def constrict_generalized_index(x, q):
    depth = last_power_of_two(x // q)
    o = depth + x - q * depth
    if concat_generalized_indices(q, o) != x:
        return None
    return o


def unrebase(objs, q):
    o = {}
    for k, v in objs.items():
        new_k = constrict_generalized_index(k, q)
        if new_k is not None:
            o[new_k] = v
    return o


def filler(starting_position, list_size, max_list_size):
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


def merkle_tree_of_chunks(chunks, max_chunk_count, root):
    starting_index = root * next_power_of_two(max_chunk_count)
    o = {starting_index + i: chunk for i, chunk in enumerate(chunks)}
    o = {**o, **filler(starting_index, len(chunks), max_chunk_count)}
    return o


def ssz_leaves(obj, typ=None, root=1):
    if is_list_kind(typ):
        o = {root * 2 + 1: len(obj).to_bytes(32, 'little')}
        base = root * 2
    else:
        o = {}
        base = root
    if is_bottom_layer_kind(typ):
        data = serialize_basic(obj, typ) if is_basic_type(typ) else pack(obj, typ.elem_type)
        return {**o, **merkle_tree_of_chunks(chunkify(data), chunk_count(typ), base)}
    else:
        fields = get_typed_values(obj, typ=typ)
        sub_base = base * next_power_of_two(chunk_count(typ))
        for i, (elem, elem_type) in enumerate(fields):
            o = {**o, **ssz_leaves(elem, typ=elem_type, root=sub_base + i)}
        return {**o, **filler(sub_base, len(fields), chunk_count(typ))}


def fill(objects):
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


@infer_input_type
def ssz_full(obj, typ=None):
    return fill(ssz_leaves(obj, typ=typ))


def get_item_position(typ, index):
    if is_basic_type(typ):
        return 0, 0, item_length(typ)
    elif is_list_kind(typ) or is_vector_kind(typ):
        start = index * item_length(typ.elem_type)
        return start // 32, start % 32, start % 32 + item_length(typ.elem_type)
    else:
        return typ.get_field_names().index(index), 0, item_length(get_elem_type(typ, index))


def get_elem_type(typ, index):
    return typ.get_fields_dict()[index] if is_container_type(typ) else typ.elem_type


def get_generalized_index(typ, root, path):
    for p in path:
        pos, _, _ = get_item_position(typ, p)
        root = root * (2 if is_list_kind(typ) else 1) * next_power_of_two(chunk_count(typ)) + pos
        typ = get_elem_type(typ, p)
    return root


def get_branch_indices(tree_index):
    o = [tree_index ^ 1]
    while o[-1] > 1:
        o.append((o[-1] // 2) ^ 1)
    return o[:-1]

def expand_indices(indices):
    branches = set()
    for index in indices:
        branches = branches.union(set(get_branch_indices(index) + [index]))
    return sorted(list([x for x in branches if x*2 not in branches or x*2+1 not in branches]))[::-1]


def remove_redundant_indices(obj):
    return {k: v for k, v in obj.items() if not (k * 2 in obj and k * 2 + 1 in obj)}


def merge(*args):
    o = {}
    for arg in args:
        o = {**o, **arg.objects}
    return ssz_partial(args[0].typ, fill(o))


class OutOfRangeException(Exception):
    pass


class SSZPartial():
    def __init__(self, typ, objects, root=1):
        assert not is_basic_type(typ)
        self.objects = objects
        self.typ = typ
        self.root = root

    def getter(self, index):
        base = self.root * 2 if is_list_kind(self.typ) else self.root
        if is_basic_type(get_elem_type(self.typ, index)):
            pos, start, end = get_item_position(self.typ, index)
            tree_index = base * next_power_of_two(chunk_count(self.typ)) + pos
            if tree_index not in self.objects:
                raise OutOfRangeException("Do not have required data")
            else:
                return deserialize_basic(
                    self.objects[tree_index][start:end],
                    self.typ if is_basic_type(self.typ) else get_elem_type(self.typ, index)
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
        base = self.root * 2 if is_list_kind(self.typ) else self.root
        elem_type = get_elem_type(self.typ, index)
        if is_basic_type(elem_type):
            pos, start, end = get_item_position(self.typ, index)
            tree_index = base * next_power_of_two(chunk_count(self.typ)) + pos
            if tree_index not in self.objects:
                raise OutOfRangeException("Do not have required data")
            else:
                chunk = self.objects[tree_index]
                self.objects[tree_index] = chunk[:start] + serialize_basic(value, elem_type) + chunk[end:]
                assert len(self.objects[tree_index]) == 32
        else:
            tree_index = get_generalized_index(self.typ, self.root, [index])
            self.clear_subtree(tree_index)
            for k, v in fill(ssz_leaves(value, elem_type, tree_index)).items():
                self.objects[k] = v
        if renew:
            self.renew_branch(tree_index)

    def append_or_pop(self, appending, value):
        assert is_list_kind(self.typ)
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
        start_pos = self.root * 2 * next_power_of_two(chunk_count(self.typ))
        if new_chunk_count != old_chunk_count:
            for k, v in filler(start_pos, old_chunk_count, chunk_count(self.typ)).items():
                del self.objects[k]
        if not appending:
            if is_basic_type(elem_type):
                self.setter(old_length-1, get_zero_value(elem_type), renew=False)
            else: 
                self.clear_subtree(get_generalized_index(self.typ, self.root, [old_length-1]))
        else:
            self.setter(new_length-1, value, renew=False)
        if new_chunk_count != old_chunk_count:
            for k, v in filler(start_pos, new_chunk_count, chunk_count(self.typ)).items():
                self.objects[k] = v
        self.renew_branch(get_generalized_index(self.typ, self.root, [new_length-1]))

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
        return ssz_partial(self.typ, {i: self.objects[i] for i in self.objects if i in branch_keys+item_keys}, self.root)

    def __getitem__(self, index):
        return self.getter(index)

    def __iter__(self):
        return (self[i] for i in range(len(self)))

    def __len__(self):
        if is_list_kind(self.typ):
            if self.root * 2 + 1 not in self.objects:
                raise OutOfRangeException("Do not have required data: {}".format(self.root * 2 + 1))
            return int.from_bytes(self.objects[self.root * 2 + 1], 'little')
        elif is_vector_kind(self.typ):
            return self.typ.length
        elif is_container_type(self.typ):
            return len(self.typ.get_fields())
        else:
            raise Exception("Unsupported type: {}".format(self.typ))

    def full_value(self):
        if issubclass(self.typ, Bytes) or issubclass(self.typ, BytesN):
            return self.typ(bytes([self.getter(i) for i in range(len(self))]))
        elif is_list_kind(self.typ) or is_vector_kind(self.typ):
            return self.typ(*(self[i] for i in range(len(self))))
        elif is_container_type(self.typ):
            def full_value(x):
                return x.full_value() if hasattr(x, 'full_value') else x

            return self.typ(**{field: full_value(self.getter(field)) for field in self.typ.get_field_names()})
        elif is_basic_type(self.typ):
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
        if is_bottom_layer_kind(self.typ) and is_basic_type(get_elem_type(self.typ, None)):
            if is_list_kind(self.typ) and self.root*2+1 not in self.objects:
                return []
            o = list(range(
                get_generalized_index(self.typ, self.root, [0]),
                get_generalized_index(self.typ, self.root, [len(self)-1]) + 1
            ))
            return [x for x in o if x in self.objects]
        elif is_container_type(self.typ):
            o = []
            for field, elem_type in self.typ.get_fields():
                if is_basic_type(elem_type):
                    gindex = get_generalized_index(self.typ, self.root, [field])
                    if gindex in self.objects:
                        o.append(gindex)
                else:
                    o.extend(self.getter(field).minimal_indices())
            return o
        else:
            return sum([self.getter(i).minimal_indices() for i in range(len(self))], [])

    def encode(self):
        indices = self.minimal_indices()
        print(indices, expand_indices(indices), sorted(list(self.objects.keys()))[::-1])
        chunks = [self.objects[o] for o in expand_indices(indices)]
        return EncodedPartial(indices=indices, chunks=chunks)
        

def ssz_partial(typ, objects, root=1):
    ssz_type = object if typ == bool else typ

    class Partial(SSZPartial, ssz_type):
        pass

    if is_container_type(typ):
        Partial.__annotations__ = typ.__annotations__
        for field in typ.get_field_names():
            setattr(Partial, field, property(
                (lambda f: (lambda self: self.getter(f)))(field),
                (lambda f: (lambda self, v: self.setter(f, v)))(field)
            ))
    o = Partial(typ, objects, root)
    return o

class EncodedPartial(Container):
    indices: List[uint64, 2**32]
    chunks: List[BytesN[32], 2**32]

    def to_ssz(self, typ):
        expanded_indices = expand_indices(self.indices)
        return ssz_partial(typ, fill({e:c for e,c in zip(expanded_indices, self.chunks)}))
