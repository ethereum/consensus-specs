from eth2spec.utils.merkle_minimal import merkleize_chunks
from .ssz_typing import *


# SSZ Defaults
# -----------------------------


def get_zero_value(typ):
    if is_uint(typ):
        return 0
    if issubclass(typ, bool):
        return False
    if issubclass(typ, list):
        return []
    if issubclass(typ, Vector):
        return typ()
    if issubclass(typ, BytesN):
        return typ()
    if issubclass(typ, bytes):
        return b''
    if issubclass(typ, SSZContainer):
        return typ(**{f: get_zero_value(t) for f, t in typ.get_fields().items()}),


# SSZ Helpers
# -----------------------------


def pack(values, subtype):
    return b''.join([serialize(value, subtype) for value in values])


def chunkify(byte_string):
    byte_string += b'\x00' * (-len(byte_string) % 32)
    return [byte_string[i:i + 32] for i in range(0, len(byte_string), 32)]


# SSZ Serialization
# -----------------------------

BYTES_PER_LENGTH_OFFSET = 4

serialize = ssz_switch({
    ssz_bool: lambda value: b'\x01' if value else b'\x00',
    ssz_uint: lambda value, byte_len: value.to_bytes(byte_len, 'little'),
    ssz_list: lambda value, elem_typ: encode_series(value, [elem_typ] * len(value)),
    ssz_vector: lambda value, elem_typ, length: encode_series(value, [elem_typ] * length),
    ssz_container: lambda value, get_field_values, field_types: encode_series(get_field_values(value), field_types),
})

is_fixed_size = ssz_type_switch({
    ssz_basic_type: lambda: True,
    ssz_vector: lambda elem_typ: is_fixed_size(elem_typ),
    ssz_container: lambda field_types: all(is_fixed_size(f_typ) for f_typ in field_types),
    ssz_list: lambda: False,
})


# SSZ Hash-tree-root
# -----------------------------

def serialize_basic(value, typ):
    if is_uint(typ):
        return value.to_bytes(typ.byte_len, 'little')
    if issubclass(typ, bool):
        if value:
            return b'\x01'
        else:
            return b'\x00'


def pack(values, subtype):
    return b''.join([serialize_basic(value, subtype) for value in values])


def is_basic_type(typ):
    return is_uint(typ) or issubclass(typ, bool)


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

# todo: signing root
def signing_root(value, typ):
    pass


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
