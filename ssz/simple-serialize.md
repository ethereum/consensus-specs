# SimpleSerialize (SSZ)

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Constants](#constants)
- [Typing](#typing)
  - [Basic types](#basic-types)
  - [Composite types](#composite-types)
  - [Variable-size and fixed-size](#variable-size-and-fixed-size)
  - [Byte](#byte)
  - [Aliases](#aliases)
  - [Default values](#default-values)
    - [`is_zero`](#is_zero)
  - [Illegal types](#illegal-types)
    - [Compatible Merkleization](#compatible-merkleization)
- [Serialization](#serialization)
  - [`uintN`](#uintn)
  - [`boolean`](#boolean)
  - [`Bitvector[N]`](#bitvectorn)
  - [`Bitlist[N]`, `ProgressiveBitlist`](#bitlistn-progressivebitlist)
  - [Vectors, containers, progressive containers, lists, progressive lists](#vectors-containers-progressive-containers-lists-progressive-lists)
  - [Union](#union)
  - [Compatible unions](#compatible-unions)
- [Deserialization](#deserialization)
- [Merkleization](#merkleization)
- [Summaries and expansions](#summaries-and-expansions)
- [Implementations](#implementations)
- [JSON mapping](#json-mapping)

<!-- mdformat-toc end -->

## Constants

| Name                      | Value | Description                                   |
| ------------------------- | ----- | --------------------------------------------- |
| `BYTES_PER_CHUNK`         | `32`  | Number of bytes per chunk.                    |
| `BYTES_PER_LENGTH_OFFSET` | `4`   | Number of bytes per serialized length offset. |
| `BITS_PER_BYTE`           | `8`   | Number of bits per byte.                      |

## Typing

### Basic types

- `uintN`: `N`-bit unsigned integer (where `N in [8, 16, 32, 64, 128, 256]`)
- `byte`: 8-bit opaque data container, equivalent in serialization and hashing
  to `uint8`
- `boolean`: `True` or `False`

### Composite types

- **container**: ordered heterogeneous collection of values
  - python dataclass notation with key-type pairs, e.g.
  ```python
  class ContainerExample(Container):
      foo: uint64
      bar: boolean
  ```
- **progressive container** _[EIP-7495]_: ordered
  heterogeneous collection of values with stable Merkleization
  - python dataclass notation with key-type pairs, e.g.
  ```python
  class Square(ProgressiveContainer(active_fields=[1, 0, 1])):
      side: uint16  # Merkleized at field index #0 (location of first 1 in `active_fields`)
      color: uint8  # Merkleized at field index #2 (location of second 1 in `active_fields`)


  class Circle(ProgressiveContainer(active_fields=[0, 1, 1])):
      radius: uint16  # Merkleized at field index #1 (location of first 1 in `active_fields`)
      color: uint8  # Merkleized at field index #2 (location of second 1 in `active_fields`)
  ```
- **vector**: ordered fixed-length homogeneous collection, with `N` values
  - notation `Vector[type, N]`, e.g. `Vector[uint64, N]`
- **list**: ordered variable-length homogeneous collection, limited to `N`
  values
  - notation `List[type, N]`, e.g. `List[uint64, N]`
- **progressive list** _[EIP-7916]_: ordered variable-length
  homogeneous collection, without limit
  - notation `ProgressiveList[type]`, e.g. `ProgressiveList[uint64]`
- **bitvector**: ordered fixed-length collection of `boolean` values, with `N`
  bits
  - notation `Bitvector[N]`
- **bitlist**: ordered variable-length collection of `boolean` values, limited
  to `N` bits
  - notation `Bitlist[N]`
- **progressive bitlist** _[EIP-7916]_: ordered
  variable-length collection of `boolean` values, without limit
  - notation `ProgressiveBitlist`
- **union**: union type containing one of the given subtypes
  - notation `Union[type_0, type_1, ...]`, e.g. `union[None, uint64, uint32]`
- **compatible union** _[EIP-8016, currently unused]_: union type containing one
  of the given subtypes with compatible Merkleization
  - notation `CompatibleUnion({selector: type})`, e.g.
    `CompatibleUnion({1: Square, 2: Circle})`

*Note*: Both `Vector[boolean, N]` and `Bitvector[N]` are valid, yet distinct due
to their different serialization requirements. Similarly, both
`List[boolean, N]` and `Bitlist[N]` are valid, yet distinct. Generally
`Bitvector[N]`/`Bitlist[N]` are preferred because of their serialization
efficiencies.

### Variable-size and fixed-size

We recursively define "variable-size" types to be lists, progressive lists,
unions, compatible unions, bitlists, progressive bitlists, and all composite
types that contain a variable-size type. All other types are said to be
"fixed-size".

### Byte

Although the SSZ serialization of `byte` is equivalent to that of `uint8`, the
former is used for opaque data while the latter is intended as a number.

### Aliases

For convenience we alias:

- `bit` to `boolean`
- `BytesN` and `ByteVector[N]` to `Vector[byte, N]` (this is *not* a basic type)
- `ByteList[N]` to `List[byte, N]`
- `ProgressiveByteList` to `ProgressiveList[byte]`

Aliases are semantically equivalent to their underlying type and therefore share
canonical representations both in SSZ and in related formats.

### Default values

Assuming a helper function `default(type)` which returns the default value for
`type`, we can recursively define the default value for all types.

| Type                                  | Default Value                                       |
| ------------------------------------- | --------------------------------------------------- |
| `uintN`                               | `0`                                                 |
| `boolean`                             | `False`                                             |
| `Container`                           | `[default(type) for type in container]`             |
| `ProgressiveContainer(active_fields)` | `[default(type) for type in progressive_container]` |
| `Vector[type, N]`                     | `[default(type)] * N`                               |
| `Bitvector[N]`                        | `[False] * N`                                       |
| `List[type, N]`                       | `[]`                                                |
| `ProgressiveList[type]`               | `[]`                                                |
| `Bitlist[N]`                          | `[]`                                                |
| `ProgressiveBitlist`                  | `[]`                                                |
| `Union[type_0, type_1, ...]`          | `default(type_0)`                                   |
| `CompatibleUnion({selector: type})`   | n/a (error)                                         |

#### `is_zero`

An SSZ object is called zeroed (and thus, `is_zero(object)` returns true) if it
is equal to the default value for that type.

### Illegal types

- Empty vector types (`Vector[type, 0]`, `Bitvector[0]`) are illegal.
- Containers with no fields are illegal.
- `ProgressiveContainer` with no fields are illegal.
- `ProgressiveContainer` with an `active_fields` configuration of more than 256
  entries are illegal.
- `ProgressiveContainer` with an `active_fields` configuration ending in `0` are
  illegal.
- `ProgressiveContainer` with an `active_fields` configuration with a different
  count of `1` than fields are illegal.
- The `None` type option in a `Union` type is only legal as the first option
  (i.e. with index zero).
- `CompatibleUnion({})` without any type options are illegal.
- `CompatibleUnion({selector: type})` with a selector outside `uint8(1)` through
  `uint8(127)` are illegal.
- `CompatibleUnion({selector: type})` with a type option that has incompatible
  Merkleization with another type option are illegal.

#### Compatible Merkleization

- Types are compatible with themselves.
- `byte` is compatible with `uint8` and vice versa.
- `Bitlist[N]` are compatible if they share the same capacity `N`.
- `Bitvector[N]` are compatible if they share the same capacity `N`.
- `List[type, N]` are compatible if `type` is compatible and they share the same
  capacity `N`.
- `Vector[type, N]` are compatible if `type` is compatible and they share the
  same capacity `N`.
- `ProgressiveList[type]` are compatible if `type` is compatible.
- `Container` are compatible if they share the same field names in the same
  order, and all field types are compatible.
- `ProgressiveContainer(active_fields)` are compatible if all `1` entries in
  both type's `active_fields` correspond to fields with shared names and
  compatible types, and no other field name is shared across both types.
- `CompatibleUnion` are compatible with each other if all type options across
  both `CompatibleUnion` are compatible.
- All other types are incompatible.

## Serialization

We recursively define the `serialize` function which consumes an object `value`
(of the type specified) and returns a bytestring of type `bytes`.

*Note*: In the function definitions below (`serialize`, `hash_tree_root`,
`is_variable_size`, etc.) objects implicitly carry their type.

### `uintN`

```python
assert N in [8, 16, 32, 64, 128, 256]
return value.to_bytes(N // BITS_PER_BYTE, "little")
```

### `boolean`

```python
assert value in (True, False)
return b"\x01" if value is True else b"\x00"
```

### `Bitvector[N]`

```python
array = [0] * ((N + 7) // 8)
for i in range(N):
    array[i // 8] |= value[i] << (i % 8)
return bytes(array)
```

### `Bitlist[N]`, `ProgressiveBitlist`

Note that from the offset coding, the length (in bytes) of the bitlist is known.
An additional `1` bit is added to the end, at index `e` where `e` is the length
of the bitlist (not the limit), so that the length in bits will also be known.

```python
array = [0] * ((len(value) // 8) + 1)
for i in range(len(value)):
    array[i // 8] |= value[i] << (i % 8)
array[len(value) // 8] |= 1 << (len(value) % 8)
return bytes(array)
```

### Vectors, containers, progressive containers, lists, progressive lists

```python
# Recursively serialize
fixed_parts = [serialize(element) if not is_variable_size(element) else None for element in value]
variable_parts = [serialize(element) if is_variable_size(element) else b"" for element in value]

# Compute and check lengths
fixed_lengths = [len(part) if part != None else BYTES_PER_LENGTH_OFFSET for part in fixed_parts]
variable_lengths = [len(part) for part in variable_parts]
assert sum(fixed_lengths + variable_lengths) < 2 ** (BYTES_PER_LENGTH_OFFSET * BITS_PER_BYTE)

# Interleave offsets of variable-size parts with fixed-size parts
variable_offsets = [
    serialize(uint32(sum(fixed_lengths + variable_lengths[:i]))) for i in range(len(value))
]
fixed_parts = [part if part != None else variable_offsets[i] for i, part in enumerate(fixed_parts)]

# Return the concatenation of the fixed-size parts (offsets interleaved) with the variable-size parts
return b"".join(fixed_parts + variable_parts)
```

### Union

A `value` as `Union[T...]` type has properties `value.value` with the contained
value, and `value.selector` which indexes the selected `Union` type option `T`.

A `Union`:

- May have multiple selectors with the same type.
- Should not use selectors above 127 (i.e. highest bit is set), these are
  reserved for backwards compatible extensions.
- Must have at least 1 type option.
- May have `None` as first type option, i.e. `selector == 0`
- Must have at least 2 type options if the first is `None`
- Is always considered a variable-length type, even if all type options have an
  equal fixed-length.

```python
if value.value is None:
    assert value.selector == 0
    return b"\x00"
else:
    serialized_bytes = serialize(value.value)
    serialized_selector_index = value.selector.to_bytes(1, "little")
    return serialized_selector_index + serialized_bytes
```

### Compatible unions

A `value` as `CompatibleUnion({selector: type})` has properties `value.data`
with the contained value, and `value.selector` which indexes the selected type
option.

```python
return value.selector.to_bytes(1, "little") + serialize(value.data)
```

## Deserialization

Because serialization is an injective function (i.e. two distinct objects of the
same type will serialize to different values) any bytestring has at most one
object it could deserialize to.

Deserialization can be implemented using a recursive algorithm. The
deserialization of basic objects is easy, and from there we can find a simple
recursive algorithm for all fixed-size objects. For variable-size objects we
have to do one of the following depending on what kind of object it is:

- Vector/list/progressive list of a variable-size object: The serialized data
  will start with offsets of all the serialized objects
  (`BYTES_PER_LENGTH_OFFSET` bytes each).
  - Using the first offset, we can compute the length of the list (divide by
    `BYTES_PER_LENGTH_OFFSET`), as it gives us the total number of bytes in the
    offset data.
  - The size of each object in the vector/list/progressive list can be inferred
    from the difference of two offsets. To get the size of the last object, the
    total number of bytes has to be known (it is not generally possible to
    deserialize an SSZ object of unknown length)
- Containers/progressive containers follow the same principles as vectors, with
  the difference that there may be fixed-size objects in a container/progressive
  container as well. This means the `fixed_parts` data will contain offsets as
  well as fixed-size objects.
- In the case of bitlists/progressive bitlists, the length in bits cannot be
  uniquely inferred from the number of bytes in the object. Because of this,
  they have a bit at the end that is always set. This bit has to be used to
  infer the size of the bitlist in bits.
- In the case of unions/compatible unions, the first byte of the deserialization
  scope is deserialized as type selector, the remainder of the scope is
  deserialized as the selected type.

Note that deserialization requires hardening against invalid inputs. A
non-exhaustive list:

- Offsets: out of order, out of range, mismatching minimum element size.
- Scope: Extra unused bytes, not aligned with element size.
- More elements than a list limit allows. Part of enforcing consensus.
- An out-of-bounds selected index in an `Union`.
- An out-of-bounds type selector in a `CompatibleUnion`.

Efficient algorithms for computing this object can be found in
[the implementations](#implementations).

## Merkleization

We first define helper functions:

- `size_of(B)`, where `B` is a basic type: the length, in bytes, of the
  serialized form of the basic type.
- `chunk_count(type)`: calculate the amount of leaves for merkleization of the
  type.
  - all basic types: `1`
  - `Bitlist[N]` and `Bitvector[N]`: `(N + 255) // 256` (dividing by chunk size,
    rounding up)
  - `List[B, N]` and `Vector[B, N]`, where `B` is a basic type:
    `(N * size_of(B) + 31) // 32` (dividing by chunk size, rounding up)
  - `List[C, N]` and `Vector[C, N]`, where `C` is a composite type: `N`
  - containers: `len(fields)`
- `get_active_fields(value)`, where `value` is of type
  `ProgressiveContainer(active_fields)`: return `active_fields`.
- `pack(values)`: Given ordered objects of the same basic type:
  1. Serialize `values` into bytes.
  2. If not aligned to a multiple of `BYTES_PER_CHUNK` bytes, right-pad with
     zeroes to the next multiple.
  3. Partition the bytes into `BYTES_PER_CHUNK`-byte chunks.
  4. Return the chunks.
- `pack_bits(bits)`: Given the bits of bitlist or bitvector, get
  `bitfield_bytes` by packing them in bytes and aligning to the start. The
  length-delimiting bit for bitlists is excluded. Then return
  `pack(bitfield_bytes)`.
- `next_pow_of_two(i)`: get the next power of 2 of `i`, if not already a power
  of 2, with 0 mapping to 1. Examples:
  `0->1, 1->1, 2->2, 3->4, 4->4, 6->8, 9->16`
- `merkleize(chunks, limit=None)`: Given ordered `BYTES_PER_CHUNK`-byte chunks,
  merkleize the chunks, and return the root:
  - The merkleization depends on the effective input, which must be
    padded/limited:
    - if no limit: pad the `chunks` with zeroed chunks to
      `next_pow_of_two(len(chunks))` (virtually for memory efficiency).
    - if `limit >= len(chunks)`, pad the `chunks` with zeroed chunks to
      `next_pow_of_two(limit)` (virtually for memory efficiency).
    - if `limit < len(chunks)`: do not merkleize, input exceeds limit. Raise an
      error instead.
  - Then, merkleize the chunks (empty input is padded to 1 zero chunk):
    - If `1` chunk: the root is the chunk itself.
    - If `> 1` chunks: merkleize as binary tree.
- `merkleize_progressive(chunks, num_leaves=1)`: Given ordered
  `BYTES_PER_CHUNK`-byte chunks:
  - The merkleization depends on the number of input chunks and is defined
    recursively:
    - If `len(chunks) == 0`: the root is a zero value, `Bytes32()`.
    - Otherwise: compute the root using `hash(a, b)`
      - `a`: Recursively merkleize chunks beyond `num_leaves` using
        `merkleize_progressive(chunks[num_leaves:], num_leaves * 4)`.
      - `b`: Merkleize the first up to `num_leaves` chunks as a binary tree
        using `merkleize(chunks[:num_leaves], num_leaves)`.
- `mix_in_active_fields`: Given a Merkle root `root` and an `active_fields`
  configuration return `hash(root, pack_bits(active_fields))`. Note that
  `active_fields` is restricted to ≤ 256 bits.
- `mix_in_length`: Given a Merkle root `root` and a length `length` (`"uint256"`
  little-endian serialization) return `hash(root, length)`.
- `mix_in_selector`: Given a Merkle root `root` and a type selector `selector`
  (`"uint8"` serialization) return `hash(root, selector)`.

We now define Merkleization `hash_tree_root(value)` of an object `value`
recursively:

- `merkleize(pack(value))` if `value` is a basic object or a vector of basic
  objects.
- `merkleize(pack_bits(value), limit=chunk_count(type))` if `value` is a
  bitvector.
- `mix_in_length(merkleize(pack(value), limit=chunk_count(type)), len(value))`
  if `value` is a list of basic objects.
- `mix_in_length(merkleize_progressive(pack(value)), len(value))` if `value` is
  a progressive list of basic objects.
- `mix_in_length(merkleize(pack_bits(value), limit=chunk_count(type)), len(value))`
  if `value` is a bitlist.
- `mix_in_length(merkleize_progressive(pack_bits(value)), len(value))` if
  `value` is a progressive bitlist.
- `merkleize([hash_tree_root(element) for element in value])` if `value` is a
  vector of composite objects or a container.
- `mix_in_active_fields(merkleize_progressive([hash_tree_root(element) for element in value]), get_active_fields(value))`
  if `value` is a progressive container.
- `mix_in_length(merkleize([hash_tree_root(element) for element in value], limit=chunk_count(type)), len(value))`
  if `value` is a list of composite objects.
- `mix_in_length(merkleize_progressive([hash_tree_root(element) for element in value]), len(value))`
  if `value` is a progressive list of composite objects.
- `mix_in_selector(hash_tree_root(value.value), value.selector)` if `value` is
  of union type, and `value.value` is not `None`
- `mix_in_selector(Bytes32(), 0)` if `value` is of union type, and `value.value`
  is `None`
- `mix_in_selector(hash_tree_root(value.data), value.selector)` if `value` is of
  compatible union type.

## Summaries and expansions

Let `A` be an object derived from another object `B` by replacing some of the
(possibly nested) values of `B` by their `hash_tree_root`. We say `A` is a
"summary" of `B`, and that `B` is an "expansion" of `A`. Notice
`hash_tree_root(A) == hash_tree_root(B)`.

We similarly define "summary types" and "expansion types". For example,
[`BeaconBlock`](../specs/phase0/beacon-chain.md#beaconblock) is an expansion
type of
[`BeaconBlockHeader`](../specs/phase0/beacon-chain.md#beaconblockheader). Notice
that objects expand to at most one object of a given expansion type. For
example, `BeaconBlockHeader` objects uniquely expand to `BeaconBlock` objects.

## Implementations

See https://github.com/ethereum/consensus-specs/issues/2138 for a list of
current known implementations.

## JSON mapping

The canonical JSON mapping assigns to each SSZ type a corresponding JSON
encoding, enabling an SSZ schema to also define the JSON encoding.

When decoding JSON data, all fields in the SSZ schema must be present with a
value. Parsers may ignore additional JSON fields.

| SSZ                                   | JSON            | Example                                  |
| ------------------------------------- | --------------- | ---------------------------------------- |
| `uintN`                               | string          | `"0"`                                    |
| `byte`                                | hex-byte-string | `"0x00"`                                 |
| `boolean`                             | bool            | `false`                                  |
| `Container`                           | object          | `{ "field": ... }`                       |
| `ProgressiveContainer(active_fields)` | object          | `{ "field": ... }`                       |
| `Vector[type, N]`                     | array           | `[element, ...]`                         |
| `Vector[byte, N]`                     | hex-byte-string | `"0x1122"`                               |
| `Bitvector[N]`                        | hex-byte-string | `"0x1122"`                               |
| `List[type, N]`                       | array           | `[element, ...]`                         |
| `List[byte, N]`                       | hex-byte-string | `"0x1122"`                               |
| `ProgressiveList[type]`               | array           | `[element, ...]`                         |
| `ProgressiveList[byte]`               | hex-byte-string | `"0x1122"`                               |
| `Bitlist[N]`                          | hex-byte-string | `"0x1122"`                               |
| `ProgressiveBitlist`                  | hex-byte-string | `"0x1122"`                               |
| `Union[type_0, type_1, ...]`          | selector-object | `{ "selector": number, "data": type_N }` |
| `CompatibleUnion({selector: type})`   | selector-object | `{ "selector": string, "data": type }`   |

Integers are encoded as strings to avoid loss of precision in 64-bit values.

Aliases are encoded as their underlying type.

`hex-byte-string` is a `0x`-prefixed hex encoding of byte data, as it would
appear in an SSZ stream.

`List`, `ProgressiveList`, and `Vector` of `byte` (and aliases thereof) are
encoded as `hex-byte-string`. `Bitlist`, `ProgressiveBitlist`, and `Bitvector`
similarly map their SSZ-byte encodings to a `hex-byte-string`.

`Union` and `CompatibleUnion` are encoded as an object with a `selector` and
`data` field, where the contents of `data` change according to the selector.
