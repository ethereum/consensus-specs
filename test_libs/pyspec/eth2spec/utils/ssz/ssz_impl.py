from ..merkle_minimal import merkleize_chunks, hash
from .ssz_typing import *

# SSZ Serialization
# -----------------------------

BYTES_PER_LENGTH_OFFSET = 4

def is_basic_type(typ):
    return is_uint(typ) or typ == bool

def serialize_basic(value, typ):
    if is_uint(typ):
        return value.to_bytes(typ.byte_len, 'little')
    if issubclass(typ, bool):
        if value:
            return b'\x01'
        else:
            return b'\x00'

def is_fixed_size(typ):
    if is_basic_type(typ):
        return True
    elif is_list_type(typ):
        return False
    elif is_vector_type(typ):
        return is_fixed_size(read_vector_elem_typ(typ))
    elif is_container_typ(typ):
        return all([is_fixed_size(t) for t in typ.get_field_types()])
    else:
        raise Exception("Type not supported: {}".format(typ))

def serialize(obj, typ=None):
    if typ is None:
        typ = infer_type(obj)
    if is_basic_type(typ):
        return serialize_basic(obj, typ)
    elif is_list_type(typ) or is_vector_type(typ):
        return encode_series(list(obj), [read_elem_typ(typ)]*len(obj))
    elif is_container_typ(typ):
        return encode_series(obj.get_field_values(), typ.get_field_types())
    else:
        raise Exception("Type not supported: {}".format(typ))

def encode_series(values, types):
    # bytes and bytesN are already in the right format.
    if isinstance(values, bytes):
        return values

    # Recursively serialize
    parts = [(is_fixed_size(types[i]), serialize(values[i], types[i])) for i in range(len(values))]

    # Compute and check lengths
    fixed_lengths = [len(serialized) if constant_size else BYTES_PER_LENGTH_OFFSET
                     for (constant_size, serialized) in parts]
    variable_lengths = [len(serialized) if not constant_size else 0
                        for (constant_size, serialized) in parts]

    # Check if integer is not out of bounds (Python)
    assert sum(fixed_lengths + variable_lengths) < 2 ** (BYTES_PER_LENGTH_OFFSET * 8)

    # Interleave offsets of variable-size parts with fixed-size parts.
    # Avoid quadratic complexity in calculation of offsets.
    offset = sum(fixed_lengths)
    variable_parts = []
    fixed_parts = []
    for (constant_size, serialized) in parts:
        if constant_size:
            fixed_parts.append(serialized)
        else:
            fixed_parts.append(offset.to_bytes(BYTES_PER_LENGTH_OFFSET, 'little'))
            variable_parts.append(serialized)
            offset += len(serialized)

    # Return the concatenation of the fixed-size parts (offsets interleaved) with the variable-size parts
    return b''.join(fixed_parts + variable_parts)

# SSZ Hash-tree-root
# -----------------------------

def pack(values, subtype):
    if isinstance(values, bytes):
        return values
    return b''.join([serialize_basic(value, subtype) for value in values])

def chunkify(bytez):
    bytez += b'\x00' * (-len(bytez) % 32)
    return [bytez[i:i + 32] for i in range(0, len(bytez), 32)]

def mix_in_length(root, length):
    return hash(root + length.to_bytes(32, 'little'))

def hash_tree_root(obj, typ=None):
    if typ is None:
        typ = infer_type(obj)
    if is_basic_type(typ):
        return merkleize_chunks(chunkify(serialize_basic(obj, typ)))
    elif is_list_type(typ) or is_vector_type(typ):
        subtype = read_elem_typ(typ)
        if is_basic_type(subtype):
            leaves = chunkify(pack(obj, subtype))
        else:
            leaves = [hash_tree_root(elem, subtype) for elem in obj]
        leaf_root = merkleize_chunks(leaves)
        return mix_in_length(leaf_root, len(obj)) if is_list_type(typ) else leaf_root
    elif is_container_typ(typ):
        leaves = [hash_tree_root(elem, subtyp) for elem, subtyp in zip(obj.get_field_values(), typ.get_field_types())]
        return merkleize_chunks(chunkify(b''.join(leaves)))
    else:
        raise Exception("Type not supported: obj {} type {}".format(obj, typ))

def signing_root(value, typ):
    if typ is None:
        typ = infer_type(obj)
    assert is_container_typ(typ)
    leaves = [hash_tree_root(elem, subtyp) for elem, subtyp in zip(obj.get_field_values(), typ.get_field_types())[:-1]]
    return merkleize_chunks(chunkify(b''.join(leaves)))

# Implementation notes:
# - SSZContainer,Vector/BytesN.hash_tree_root/serialize functions are for ease, implementation here
# - uint types have a 'byte_len' attribute
# - uint types are not classes. They use NewType(), for performance.
#    This forces us to check type equivalence by exact reference.
#    There's no class. The type data comes from an annotation/argument from the context of the value.
# - Vector is not valid to create instances with. Give it a elem-type and length: Vector[FooBar, 123]
# - *The class of* a Vector instance has a `elem_type` (type, may not be a class, see uint) and `length` (int)
# - BytesN is not valid to create instances with. Give it a length: BytesN[123]
# - *The class of* a BytesN instance has a `length` (int)
# Where possible, it is preferable to create helpers that just act on the type, and don't unnecessarily use a value
# E.g. is_basic_type(). This way, we can use them in type-only contexts and have no duplicate logic.
# For every class-instance, you can get the type with my_object.__class__
# For uints, and other NewType related, you have to rely on type information. It cannot be retrieved from the value.
# Note: we may just want to box integers instead. And then we can do bounds checking too. But it is SLOW and MEMORY INTENSIVE.
#
