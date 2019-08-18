from ..merkle_minimal import merkleize_chunks
from ..hash_function import hash
from .ssz_typing import (
    SSZValue, SSZType, BasicValue, BasicType, ComplexValue,
    ElementsType, BitElementsType, Bits, boolean, Container, List, ByteList,
    Bitlist, Bitvector, uint,
)

# SSZ Serialization
# -----------------------------

BYTES_PER_LENGTH_OFFSET = 4


def serialize_basic(value: SSZValue):
    if isinstance(value, uint):
        return value.to_bytes(value.type().byte_len, 'little')
    elif isinstance(value, boolean):
        if value:
            return b'\x01'
        else:
            return b'\x00'
    else:
        raise Exception(f"Type not supported: {type(value)}")


def is_zero(obj: SSZValue):
    return type(obj).default() == obj


def serialize(obj: SSZValue):
    if isinstance(obj, BasicValue):
        return serialize_basic(obj)
    elif isinstance(obj, Bitvector):
        return obj.as_bytes()
    elif isinstance(obj, Bitlist):
        as_bytearray = list(obj.as_bytes())
        if len(obj) % 8 == 0:
            as_bytearray.append(1)
        else:
            as_bytearray[len(obj) // 8] |= 1 << (len(obj) % 8)
        return bytes(as_bytearray)
    elif isinstance(obj, ComplexValue):
        return encode_series(obj)
    else:
        raise Exception(f"Type not supported: {type(obj)}")


def encode_series(values: ComplexValue):
    if isinstance(values, bytes):  # Bytes and BytesN are already like serialized output
        return values

    # Recursively serialize
    parts = [(v.type().is_fixed_size(), serialize(v)) for v in values]

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


def pack(values: ComplexValue):
    if isinstance(values, bytes):  # Bytes and BytesN are already packed
        return values
    elif isinstance(values, Bits):
        # packs the bits in bytes, left-aligned.
        # Exclusive length delimiting bits for bitlists.
        return values.as_bytes()
    return b''.join([serialize_basic(value) for value in values])


def chunkify(bytez):
    # pad `bytez` to nearest 32-byte multiple
    bytez += b'\x00' * (-len(bytez) % 32)
    return [bytez[i:i + 32] for i in range(0, len(bytez), 32)]


def mix_in_length(root, length):
    return hash(root + length.to_bytes(32, 'little'))


def is_bottom_layer_kind(typ: SSZType):
    return (
        isinstance(typ, BasicType) or
        (isinstance(typ, ElementsType) and isinstance(typ.elem_type, BasicType))
    )


def item_length(typ: SSZType) -> int:
    if issubclass(typ, BasicValue):
        return typ.byte_len
    else:
        return 32


def chunk_count(typ: SSZType) -> int:
    if isinstance(typ, BasicType):
        return 1
    elif isinstance(typ, BitElementsType):
        return (typ.max_elements() + 255) // 256
    elif isinstance(typ, ElementsType):
        return (typ.max_elements() * item_length(typ.elem_type) + 31) // 32
    elif issubclass(typ, Container):
        return len(typ.get_fields())
    else:
        raise Exception(f"Type not supported: {typ}")


def hash_tree_root(obj: SSZValue):
    if isinstance(obj, ComplexValue):
        if is_bottom_layer_kind(obj.type()):
            leaves = chunkify(pack(obj))
        else:
            leaves = [hash_tree_root(value) for value in obj]
    elif isinstance(obj, BasicValue):
        leaves = chunkify(serialize_basic(obj))
    else:
        raise Exception(f"Type not supported: {type(obj)}")

    if isinstance(obj, (List, ByteList, Bitlist)):
        return mix_in_length(merkleize_chunks(leaves, limit=chunk_count(obj.type())), len(obj))
    else:
        return merkleize_chunks(leaves)


def signing_root(obj: Container):
    # ignore last field
    fields = [field for field in obj][:-1]
    leaves = [hash_tree_root(f) for f in fields]
    return merkleize_chunks(chunkify(b''.join(leaves)))
