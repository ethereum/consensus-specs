from ..merkle_minimal import hash, next_power_of_two
from .ssz_typing import (
    Container,
    infer_input_type,
    is_bool_type,
    is_bytes_type,
    is_bytesn_type,
    is_container_type,
    is_list_kind,
    is_list_type,
    is_uint_type,
    is_vector_kind,
    is_vector_type,
    read_elem_type,
    uint_byte_size,
)
from .ssz_impl import (
    chunkify,
    deserialize_basic,
    get_typed_values,
    is_basic_type,
    is_bottom_layer_kind,
    pack,
    serialize_basic,
)


ZERO_CHUNK = b'\x00' * 32


def last_power_of_two(x):
    return next_power_of_two(x + 1) // 2


def concat_generalized_indices(x, y):
    return x * last_power_of_two(y) + y - last_power_of_two(y)


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


def filler(starting_position, chunk_count):
    at, skip, end = chunk_count, 1, next_power_of_two(chunk_count)
    value = ZERO_CHUNK
    o = {}
    while at < end:
        while at % (skip * 2) == 0:
            skip *= 2
            value = hash(value + value)
        o[(starting_position + at) // skip] = value
        at += skip
    return o


def merkle_tree_of_chunks(chunks, root):
    starting_index = root * next_power_of_two(len(chunks))
    o = {starting_index + i: chunk for i, chunk in enumerate(chunks)}
    o = {**o, **filler(starting_index, len(chunks))}
    return o


@infer_input_type
def ssz_leaves(obj, typ=None, root=1):
    if is_list_kind(typ):
        o = {root * 2 + 1: len(obj).to_bytes(32, 'little')}
        base = root * 2
    else:
        o = {}
        base = root
    if is_bottom_layer_kind(typ):
        data = serialize_basic(obj, typ) if is_basic_type(typ) else pack(obj, read_elem_type(typ))
        q = {**o, **merkle_tree_of_chunks(chunkify(data), base)}
        # print(obj, root, typ, base, list(q.keys()))
        return(q)
    else:
        fields = get_typed_values(obj, typ=typ)
        sub_base = base * next_power_of_two(len(fields))
        for i, (elem, elem_type) in enumerate(fields):
            o = {**o, **ssz_leaves(elem, typ=elem_type, root=sub_base + i)}
        q = {**o, **filler(sub_base, len(fields))}
        # print(obj, root, typ, base, list(q.keys()))
        return(q)


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


def get_basic_type_size(typ):
    if is_uint_type(typ):
        return uint_byte_size(typ)
    elif is_bool_type(typ):
        return 1
    else:
        raise Exception("Type not basic: {}".format(typ))


def get_bottom_layer_element_position(typ, base, length, index):
    """
    Returns the generalized index and the byte range of the index'th value
    in the list with the given base generalized index and given length
    """
    assert index < (1 if is_basic_type(typ) else length)
    elem_typ = typ if is_basic_type(typ) else read_elem_type(typ)
    elem_size = get_basic_type_size(elem_typ)
    chunk_index = index * elem_size // 32
    chunk_count = (1 if is_basic_type(typ) else length) * elem_size // 32
    generalized_index = base * next_power_of_two(chunk_count) + chunk_index
    start = elem_size * index % 32
    return generalized_index, start, start + elem_size


@infer_input_type
def get_generalized_indices(obj, path, typ=None, root=1):
    if len(path) == 0:
        return [root] if is_basic_type(typ) else list(ssz_leaves(obj, typ=typ, root=root).keys())
    if path[0] == '__len__':
        return [root * 2 + 1] if is_list_type(typ) else []
    base = root * 2 if is_list_kind(typ) else root
    if is_bottom_layer_kind(typ):
        length = 1 if is_basic_type(typ) else len(obj)
        index, _, _ = get_bottom_layer_element_position(typ, base, length, path[0])
        return [index]
    else:
        if is_container_type(typ):
            fields = typ.get_field_names()
            field_count, index = len(fields), fields.index(path[0])
            elem_type = typ.get_field_types()[index]
            child = obj.get_field_values()[index]
        else:
            field_count, index, elem_type, child = len(obj), path[0], read_elem_type(typ), obj[path[0]]
        return get_generalized_indices(
            child,
            path[1:],
            typ=elem_type,
            root=base * next_power_of_two(field_count) + index
        )


def get_branch_indices(tree_index):
    o = [tree_index, tree_index ^ 1]
    while o[-1] > 1:
        o.append((o[-1] // 2) ^ 1)
    return o[:-1]


def remove_redundant_indices(obj):
    return {k: v for k, v in obj.items() if not (k * 2 in obj and k * 2 + 1 in obj)}


def merge(*args):
    o = {}
    for arg in args:
        o = {**o, **arg}
    return fill(o)


@infer_input_type
def get_nodes_along_path(obj, path, typ=None):
    indices = get_generalized_indices(obj, path, typ=typ)
    return remove_redundant_indices(merge(
        *({i: obj.objects[i] for i in get_branch_indices(index)} for index in indices)
    ))


class OutOfRangeException(Exception):
    pass


class SSZPartial():
    def __init__(self, typ, objects, root=1):
        assert not is_basic_type(typ)
        self.objects = objects
        self.typ = typ
        self.root = root
        if is_container_type(self.typ):
            for field in self.typ.get_field_names():
                try:
                    setattr(self, field, self.getter(field))
                except OutOfRangeException:
                    pass

    def getter(self, index):
        base = self.root * 2 if is_list_kind(self.typ) else self.root
        if is_bottom_layer_kind(self.typ):
            tree_index, start, end = get_bottom_layer_element_position(
                self.typ, base, len(self), index
            )
            if tree_index not in self.objects:
                raise OutOfRangeException("Do not have required data")
            else:
                return deserialize_basic(
                    self.objects[tree_index][start:end],
                    self.typ if is_basic_type(self.typ) else read_elem_type(self.typ)
                )
        else:
            if is_container_type(self.typ):
                fields = self.typ.get_field_names()
                field_count, index = len(fields), fields.index(index)
                elem_type = self.typ.get_field_types()[index]
            else:
                field_count, index, elem_type = len(self), index, read_elem_type(self.typ)
            tree_index = base * next_power_of_two(field_count) + index
            if tree_index not in self.objects:
                raise OutOfRangeException("Do not have required data")
            if is_basic_type(elem_type):
                return deserialize_basic(self.objects[tree_index][:get_basic_type_size(elem_type)], elem_type)
            else:
                return ssz_partial(elem_type, self.objects, root=tree_index)

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
        if is_bytes_type(self.typ) or is_bytesn_type(self.typ):
            return bytes([self.getter(i) for i in range(len(self))])
        elif is_list_kind(self.typ):
            return [self[i] for i in range(len(self))]
        elif is_vector_kind(self.typ):
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


def ssz_partial(typ, objects, root=1):
    ssz_type = (
        Container if is_container_type(typ) else
        typ if (is_vector_type(typ) or is_bytesn_type(typ)) else object
    )

    class Partial(SSZPartial, ssz_type):
        pass

    if is_container_type(typ):
        Partial.__annotations__ = typ.__annotations__
    o = Partial(typ, objects, root=root)
    return o
