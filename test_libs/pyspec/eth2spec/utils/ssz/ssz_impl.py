from eth2spec.utils.merkle_minimal import merkleize_chunks
from .ssz_switch import *

# SSZ Helpers
# -----------------------------


def pack(values, subtype):
    return b''.join([serialize(value, subtype) for value in values])


def chunkify(byte_string):
    byte_string += b'\x00' * (-len(byte_string) % 32)
    return [byte_string[i:i + 32] for i in range(0, len(byte_string), 32)]


BYTES_PER_LENGTH_OFFSET = 4


# SSZ Implementation
# -----------------------------

get_zero_value = ssz_type_switch({
    ssz_bool: lambda: False,
    ssz_uint: lambda: 0,
    ssz_list: lambda byte_form: b'' if byte_form else [],
    ssz_vector: lambda length, elem_typ, byte_form:
    (b'\x00' * length if length > 0 else b'') if byte_form else
    [get_zero_value(elem_typ) for _ in range(length)],
    ssz_container: lambda typ, field_names, field_types:
    typ(**{f_name: get_zero_value(f_typ) for f_name, f_typ in zip(field_names, field_types)}),
})


serialize = ssz_switch({
    ssz_bool: lambda value: b'\x01' if value else b'\x00',
    ssz_uint: lambda value, byte_len: value.to_bytes(byte_len, 'little'),
    ssz_list: lambda value, elem_typ: encode_series(value, [elem_typ] * len(value)),
    ssz_vector: lambda value, elem_typ, length: encode_series(value, [elem_typ] * length),
    ssz_container: lambda value, get_field_values, field_types: encode_series(get_field_values(value), field_types),
})

ssz_basic_type = (ssz_bool, ssz_uint)

is_basic_type = ssz_type_switch({
    ssz_basic_type: lambda: True,
    ssz_default: lambda: False,
})

is_fixed_size = ssz_type_switch({
    ssz_basic_type: lambda: True,
    ssz_vector: lambda elem_typ: is_fixed_size(elem_typ),
    ssz_container: lambda field_types: all(is_fixed_size(f_typ) for f_typ in field_types),
    ssz_list: lambda: False,
})


def hash_tree_root_list(value, elem_typ):
    if is_basic_type(elem_typ):
        return merkleize_chunks(chunkify(pack(value, elem_typ)))
    else:
        return merkleize_chunks([hash_tree_root(element, elem_typ) for element in value])


def mix_in_length(root, length):
    return hash(root + length.to_bytes(32, 'little'))


def hash_tree_root_container(fields):
    return merkleize_chunks([hash_tree_root(field, subtype) for field, subtype in fields])


hash_tree_root = ssz_switch({
    ssz_basic_type: lambda value, typ: merkleize_chunks(chunkify(pack([value], typ))),
    ssz_list: lambda value, elem_typ: mix_in_length(hash_tree_root_list(value, elem_typ), len(value)),
    ssz_vector: lambda value, elem_typ: hash_tree_root_list(value, elem_typ),
    ssz_container: lambda value, get_field_values, field_types: hash_tree_root_container(zip(get_field_values(value), field_types)),
})

signing_root = ssz_switch({
    ssz_container: lambda value, get_field_values, field_types: hash_tree_root_container(zip(get_field_values(value), field_types)[:-1]),
    ssz_default: lambda value, typ: hash_tree_root(value, typ),
})


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
