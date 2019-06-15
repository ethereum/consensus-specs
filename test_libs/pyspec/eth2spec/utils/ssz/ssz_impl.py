from ..merkle_minimal import merkleize_chunks, ZERO_BYTES32
from ..hash_function import hash
from .ssz_typing import (
    get_zero_value, Container, List, Vector, Bytes, BytesN, uint
)

# SSZ Serialization
# -----------------------------

BYTES_PER_LENGTH_OFFSET = 4


def is_basic_type(typ):
    return issubclass(typ, (bool, uint))


def serialize_basic(value, typ):
    if issubclass(typ, uint):
        return value.to_bytes(typ.byte_len, 'little')
    elif issubclass(typ, bool):
        if value:
            return b'\x01'
        else:
            return b'\x00'
    else:
        raise Exception("Type not supported: {}".format(typ))


def deserialize_basic(value, typ):
    if issubclass(typ, uint):
        return typ(int.from_bytes(value, 'little'))
    elif issubclass(typ, bool):
        assert value in (b'\x00', b'\x01')
        return True if value == b'\x01' else False
    else:
        raise Exception("Type not supported: {}".format(typ))


def is_list_kind(typ):
    return issubclass(typ, (List, Bytes))


def is_vector_kind(typ):
    return issubclass(typ, (Vector, BytesN))


def is_container_type(typ):
    return issubclass(typ, Container)


def is_fixed_size(typ):
    if is_basic_type(typ):
        return True
    elif is_list_kind(typ):
        return False
    elif is_vector_kind(typ):
        return is_fixed_size(typ.elem_type)
    elif is_container_type(typ):
        return all(is_fixed_size(t) for t in typ.get_field_types())
    else:
        raise Exception("Type not supported: {}".format(typ))


def is_empty(obj):
    return get_zero_value(type(obj)) == obj


def serialize(obj, typ):
    if is_basic_type(typ):
        return serialize_basic(obj, typ)
    elif is_list_kind(typ) or is_vector_kind(typ):
        return encode_series(obj, [typ.elem_type] * len(obj))
    elif is_container_type(typ):
        return encode_series(obj.get_field_values(), typ.get_field_types())
    else:
        raise Exception("Type not supported: {}".format(typ))


def encode_series(values, types):
    # bytes and bytesN are already in the right format.
    if isinstance(values, bytes):
        return values

    # Recursively serialize
    parts = [(is_fixed_size(types[i]), serialize(values[i], typ=types[i])) for i in range(len(values))]

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
    # pad `bytez` to nearest 32-byte multiple
    bytez += b'\x00' * (-len(bytez) % 32)
    return [bytez[i:i + 32] for i in range(0, len(bytez), 32)]


def mix_in_length(root, length):
    return hash(root + length.to_bytes(32, 'little'))


def is_bottom_layer_kind(typ):
    return (
        is_basic_type(typ) or
        (is_list_kind(typ) or is_vector_kind(typ)) and is_basic_type(typ.elem_type)
    )


def get_typed_values(obj, typ):
    if is_container_type(typ):
        return obj.get_typed_values()
    elif is_list_kind(typ) or is_vector_kind(typ):
        return list(zip(obj, [typ.elem_type] * len(obj)))
    else:
        raise Exception("Invalid type")


def item_length(typ):
    if typ == bool:
        return 1
    elif issubclass(typ, uint):
        return typ.byte_len
    else:
        return 32
def chunk_count(typ):
    if is_basic_type(typ):
       return 1
   elif is_list_kind(typ) or is_vector_kind(typ):
       return (typ.length * item_length(typ.elem_type) + 31) // 32
   else:
       return len(typ.get_fields())

def hash_tree_root(obj, typ):
    if is_bottom_layer_kind(typ):
        data = serialize_basic(obj, typ) if is_basic_type(typ) else pack(obj, typ.elem_type)
        leaves = chunkify(data)
    else:
        fields = get_typed_values(obj, typ=typ)
        leaves = [hash_tree_root(field_value, typ=field_typ) for field_value, field_typ in fields]
    if is_list_kind(typ):
        return mix_in_length(merkleize_chunks(leaves, pad_to=typ.length), len(obj))
    else:
        return merkleize_chunks(leaves)


def signing_root(obj, typ):
    assert is_container_type(typ)
    # ignore last field
    leaves = [hash_tree_root(field_value, typ=field_typ) for field_value, field_typ in obj.get_typed_values()[:-1]]
    return merkleize_chunks(chunkify(b''.join(leaves)))
