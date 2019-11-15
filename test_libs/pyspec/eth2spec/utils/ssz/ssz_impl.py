from ..merkle_minimal import merkleize_chunks
from ..hash_function import hash
from .ssz_typing import (
    SSZValue, SSZType, BasicValue, BasicType, Series, Elements, Bits, boolean, Container, List, ByteList, Vector,
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


def deserialize_basic(value, typ: BasicType):
    if issubclass(typ, uint):
        return typ(int.from_bytes(value, 'little'))
    elif issubclass(typ, boolean):
        assert value in (b'\x00', b'\x01')
        return typ(value == b'\x01')
    else:
        raise Exception(f"Type not supported: {typ}")


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
    elif isinstance(obj, Series):
        return encode_series(obj)
    else:
        raise Exception(f"Type not supported: {type(obj)}")


def encode_series(values: Series):
    if isinstance(values, bytes):  # ByteList and ByteVector are already like serialized output
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


def pack(values: Series):
    if isinstance(values, bytes):  # ByteList and ByteVector are already packed
        return values
    elif isinstance(values, Bits):
        # packs the bits in bytes, left-aligned.
        # Exclusive length delimiting bits for bitlists.
        return values.as_bytes()
    return b''.join([serialize_basic(value) for value in values])


def basic_to_chunk(value: BasicValue) -> bytes:
    b = serialize_basic(value)
    b += b'\x00' * (32 - len(b))
    return b


def bytes_to_chunks(bytez) -> list:
    if len(bytez) == 32:  # common case
        return [bytez]

    # pad `bytez` to nearest 32-byte multiple
    bytez += b'\x00' * (-len(bytez) % 32)
    return [bytez[i:i + 32] for i in range(0, len(bytez), 32)]


def chunkify(values) -> (list, int):
    if isinstance(values, bytes):  # ByteList and ByteVector are already packed
        return bytes_to_chunks(values), 0
    elif isinstance(values, Bits):
        # packs the bits in bytes, left-aligned.
        # Exclusive length delimiting bits for bitlists.
        return bytes_to_chunks(values.as_bytes()), 0
    elif isinstance(values, Vector) and values.is_caching():
        cache_layer = values._cache_partitions_
        partition_size = values._partition_size_
        for i in range(len(cache_layer)):
            if cache_layer[i] is None:
                partition = Vector[values.type().elem_type, partition_size](
                    values[i * partition_size:(i + 1) * partition_size])
                partition._is_caching_ = False
                cache_layer[i] = hash_tree_root(partition)
        return cache_layer, partition_size.bit_length()
    elif is_bottom_layer_kind(values.type()):
        return bytes_to_chunks(pack(values)), 0
    else:
        return [hash_tree_root(value) for value in values], 0


def mix_in_length(root, length):
    return hash(root + length.to_bytes(32, 'little'))


def is_bottom_layer_kind(typ: SSZType):
    return (
        isinstance(typ, BasicType) or
        (issubclass(typ, Elements) and isinstance(typ.elem_type, BasicType))
    )


def item_length(typ: SSZType) -> int:
    if issubclass(typ, BasicValue):
        return typ.byte_len
    else:
        return 32


def chunk_count(typ: SSZType) -> int:
    # note that for lists, .length *on the type* describes the list limit.
    if isinstance(typ, BasicType):
        return 1
    elif issubclass(typ, Bits):
        return (typ.length + 255) // 256
    elif issubclass(typ, Elements):
        return (typ.length * item_length(typ.elem_type) + 31) // 32
    elif issubclass(typ, Container):
        return len(typ.get_fields())
    else:
        raise Exception(f"Type not supported: {typ}")


def hash_tree_root(obj: SSZValue):
    if isinstance(obj, Series):
        chunks, depth = chunkify(obj)

        if isinstance(obj, (List, ByteList, Bitlist)):
            return mix_in_length(merkleize_chunks(chunks, limit=chunk_count(obj.type()) >> depth), len(obj))
        else:
            return merkleize_chunks(chunks)

    elif isinstance(obj, BasicValue):
        return basic_to_chunk(obj)
    else:
        raise Exception(f"Type not supported: {type(obj)}")


def signing_root(obj: Container):
    # ignore last field
    fields = [field for field in obj][:-1]
    leaves = [hash_tree_root(f) for f in fields]
    return merkleize_chunks(leaves)
