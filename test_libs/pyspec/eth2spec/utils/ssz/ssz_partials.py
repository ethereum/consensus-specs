from ..merkle_minimal import hash, next_power_of_two
from .ssz_typing import *
from .ssz_impl import *

ZERO_CHUNK = b'\x00' * 32

def last_power_of_two(x):
    return next_power_of_two(x+1) // 2

def concat_generalized_indices(x, y):
    return x * last_power_of_two(y) + y - last_power_of_two(y)

def rebase(objs, new_root):
    return {concat_generalized_indices(new_root, k): v for k,v in objs.items()}

def constrict_generalized_index(x, q):
    depth = last_power_of_two(x // q)
    o = depth + x - q * depth
    if concat_generalized_indices(q, o) != x:
        return None
    return o

def unrebase(objs, q):
    o = {}
    for k,v in objs.items():
        new_k = constrict_generalized_index(k, q)
        if new_k is not None:
            o[new_k] = v
    return o

def filler(starting_position, chunk_count):
    at, skip, end = chunk_count, 1, next_power_of_two(chunk_count)
    value = ZERO_CHUNK
    o = {}
    while at < end:
        while at % (skip*2) == 0:
            skip *= 2
            value = hash(value + value)
        o[starting_position + at] = value
        at += skip
    return o

def merkle_tree_of_chunks(chunks, root):
    starting_index = root * next_power_of_two(len(chunks))
    o = {starting_index+i: chunk for i,chunk in enumerate(chunks)}
    o = {**o, **filler(starting_index, len(chunks))}
    return o

@infer_input_type
def ssz_all(obj, typ=None, root=1):
    if is_list_type(typ):
        o = {root * 2 + 1: len(obj).to_bytes(32, 'little')}
        base = root * 2
    else:
        o = {}
        base = root
    if is_bottom_layer_type(typ):
        data = serialize_basic(obj, typ) if is_basic_type(typ) else pack(obj, read_elem_typ(typ))
        return {**o, **merkle_tree_of_chunks(chunkify(data), base)}
    else:
        fields = get_typed_values(obj, typ=typ)
        sub_base = base * next_power_of_two(len(fields))
        for i, (elem, elem_type) in enumerate(fields):
            o = {**o, **ssz_all(elem, typ=elem_type, root=sub_base+i)}
        return {**o, **filter(sub_base, len(fields))}
