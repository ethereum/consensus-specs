# SimpleSerialize (SSZ)

**Notice**: This document is a work-in-progress describing typing, serialization, and Merkleization of Eth 2.0 objects.

## Table of contents
<!-- TOC -->

- [SimpleSerialize (SSZ)](#simpleserialize-ssz)
    - [Table of contents](#table-of-contents)
    - [Constants](#constants)
    - [Typing](#typing)
        - [Basic types](#basic-types)
        - [Composite types](#composite-types)
        - [Variable-size and fixed-size](#variable-size-and-fixed-size)
        - [Aliases](#aliases)
        - [Default values](#default-values)
            - [`is_empty`](#is_empty)
        - [Illegal types](#illegal-types)
    - [Serialization](#serialization)
        - [`uintN`](#uintn)
        - [`boolean`](#boolean)
        - [`null`](#null)
        - [`Bitvector[N]`](#bitvectorn)
        - [`Bitlist[N]`](#bitlistn)
        - [Vectors, containers, lists, unions](#vectors-containers-lists-unions)
    - [Deserialization](#deserialization)
    - [Merkleization](#merkleization)
    - [Self-signed containers](#self-signed-containers)
    - [Implementations](#implementations)

<!-- /TOC -->

## Constants

| Name | Value | Description |
|-|-|-|
| `BYTES_PER_CHUNK` | `32` | Number of bytes per chunk. |
| `BYTES_PER_LENGTH_OFFSET` | `4` | Number of bytes per serialized length offset. |
| `BITS_PER_BYTE` | `8` | Number of bits per byte. |

## Typing
### Basic types

* `uintN`: `N`-bit unsigned integer (where `N in [8, 16, 32, 64, 128, 256]`)
* `boolean`: `True` or `False`

### Composite types

* **container**: ordered heterogeneous collection of values
    * python dataclass notation with key-type pairs, e.g.
    ```python
    class ContainerExample(Container):
        foo: uint64
        bar: boolean
    ```
* **vector**: ordered fixed-length homogeneous collection, with `N` values
    * notation `Vector[type, N]`, e.g. `Vector[uint64, N]`
* **list**: ordered variable-length homogeneous collection, limited to `N` values
    * notation `List[type, N]`, e.g. `List[uint64, N]`
* **bitvector**: ordered fixed-length collection of `boolean` values, with `N` bits
    * notation `Bitvector[N]`
* **bitlist**: ordered variable-length collection of `boolean` values, limited to `N` bits
    * notation `Bitlist[N]`
* **union**: union type containing one of the given subtypes
    * notation `Union[type_1, type_2, ...]`, e.g. `union[null, uint64]`

### Variable-size and fixed-size

We recursively define "variable-size" types to be lists, unions, `Bitlist` and all types that contain a variable-size type. All other types are said to be "fixed-size".

### Aliases

For convenience we alias:

* `bit` to `boolean`
* `byte` to `uint8` (this is a basic type)
* `BytesN` to `Vector[byte, N]` (this is *not* a basic type)
* `null`: `{}`

### Default values

The default value of a type upon initialization is recursively defined using `0` for `uintN`, `False` for `boolean` and the elements of `Bitvector`, and `[]` for lists and `Bitlist`. Unions default to the first type in the union (with type index zero), which is `null` if present in the union.

#### `is_empty`

An SSZ object is called empty (and thus, `is_empty(object)` returns true) if it is equal to the default value for that type.

### Illegal types

- Empty vector types (`Vector[type, 0]`, `Bitvector[0]`) are illegal.
- Containers with no fields are illegal.
- The `null` type is only legal as the first type in a union subtype (i.e. with type index zero).

## Serialization

We recursively define the `serialize` function which consumes an object `value` (of the type specified) and returns a bytestring of type `bytes`.

*Note*: In the function definitions below (`serialize`, `hash_tree_root`, `signing_root`, `is_variable_size`, etc.) objects implicitly carry their type.

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

### `null`

```python
return b""
```

### `Bitvector[N]`

```python
array = [0] * ((N + 7) // 8)
for i in range(N):
    array[i // 8] |= value[i] << (i % 8)
return bytes(array)
```

### `Bitlist[N]`

Note that from the offset coding, the length (in bytes) of the bitlist is known. An additional leading `1` bit is added so that the length in bits will also be known.

```python
array = [0] * ((len(value) // 8) + 1)
for i in range(len(value)):
    array[i // 8] |= value[i] << (i % 8)
array[len(value) // 8] |= 1 << (len(value) % 8)
return bytes(array)
```

### Vectors, containers, lists, unions

```python
# Recursively serialize
fixed_parts = [serialize(element) if not is_variable_size(element) else None for element in value]
variable_parts = [serialize(element) if is_variable_size(element) else b"" for element in value]

# Compute and check lengths
fixed_lengths = [len(part) if part != None else BYTES_PER_LENGTH_OFFSET for part in fixed_parts]
variable_lengths = [len(part) for part in variable_parts]
assert sum(fixed_lengths + variable_lengths) < 2**(BYTES_PER_LENGTH_OFFSET * BITS_PER_BYTE)

# Interleave offsets of variable-size parts with fixed-size parts
variable_offsets = [serialize(sum(fixed_lengths + variable_lengths[:i])) for i in range(len(value))]
fixed_parts = [part if part != None else variable_offsets[i] for i, part in enumerate(fixed_parts)]

# Return the concatenation of the fixed-size parts (offsets interleaved) with the variable-size parts
return b"".join(fixed_parts + variable_parts)
```

If `value` is a union type:

Define value as an object that has properties `value.value` with the contained value, and `value.type_index` which indexes the type.

```python
serialized_bytes = serialize(value.value)
serialized_type_index = value.type_index.to_bytes(BYTES_PER_LENGTH_OFFSET, "little")
return serialized_type_index + serialized_bytes
```

## Deserialization

Because serialization is an injective function (i.e. two distinct objects of the same type will serialize to different values) any bytestring has at most one object it could deserialize to. Efficient algorithms for computing this object can be found in [the implementations](#implementations).

Note that deserialization requires hardening against invalid inputs. A non-exhaustive list:

- Offsets: out of order, out of range, mismatching minimum element size.
- Scope: Extra unused bytes, not aligned with element size.
- More elements than a list limit allows. Part of enforcing consensus.

## Merkleization

We first define helper functions:

* `size_of(B)`, where `B` is a basic type: the length, in bytes, of the serialized form of the basic type.
* `chunk_count(type)`: calculate the amount of leafs for merkleization of the type.
   * all basic types: `1`
   * `Bitlist[N]` and `Bitvector[N]`: `(N + 255) // 256` (dividing by chunk size, rounding up)
   * `List[B, N]` and `Vector[B, N]`, where `B` is a basic type: `(N * size_of(B) + 31) // 32` (dividing by chunk size, rounding up)
   * `List[C, N]` and `Vector[C, N]`, where `C` is a composite type: `N`
   * containers: `len(fields)`
* `bitfield_bytes(bits)`: return the bits of the bitlist or bitvector, packed in bytes, aligned to the start. Exclusive length-delimiting bit for bitlists.
* `pack`: Given ordered objects of the same basic type, serialize them, pack them into `BYTES_PER_CHUNK`-byte chunks, right-pad the last chunk with zero bytes, and return the chunks.
* `next_pow_of_two(i)`: get the next power of 2 of `i`, if not already a power of 2, with 0 mapping to 1. Examples: `0->1, 1->1, 2->2, 3->4, 4->4, 6->8, 9->16`
* `merkleize(chunks, limit=None)`: Given ordered `BYTES_PER_CHUNK`-byte chunks, merkleize the chunks, and return the root:
    * The merkleization depends on the effective input, which can be padded/limited:
        - if no limit: pad the `chunks` with zeroed chunks to `next_pow_of_two(len(chunks))` (virtually for memory efficiency).
        - if `limit > len(chunks)`, pad the `chunks` with zeroed chunks to `next_pow_of_two(limit)` (virtually for memory efficiency).
        - if `limit < len(chunks)`: do not merkleize, input exceeds limit. Raise an error instead.
    * Then, merkleize the chunks (empty input is padded to 1 zero chunk):
        - If `1` chunk: the root is the chunk itself.
        - If `> 1` chunks: merkleize as binary tree.
* `mix_in_length`: Given a Merkle root `root` and a length `length` (`"uint256"` little-endian serialization) return `hash(root + length)`.
* `mix_in_type`: Given a Merkle root `root` and a type_index `type_index` (`"uint256"` little-endian serialization) return `hash(root + type_index)`.

We now define Merkleization `hash_tree_root(value)` of an object `value` recursively:

* `merkleize(pack(value))` if `value` is a basic object or a vector of basic objects.
* `merkleize(bitfield_bytes(value), limit=chunk_count(type))` if `value` is a bitvector.
* `mix_in_length(merkleize(pack(value), limit=chunk_count(type)), len(value))` if `value` is a list of basic objects.
* `mix_in_length(merkleize(bitfield_bytes(value), limit=chunk_count(type)), len(value))` if `value` is a bitlist.
* `merkleize([hash_tree_root(element) for element in value])` if `value` is a vector of composite objects or a container.
* `mix_in_length(merkleize([hash_tree_root(element) for element in value], limit=chunk_count(type)), len(value))` if `value` is a list of composite objects.
* `mix_in_type(merkleize(value.value), value.type_index)` if `value` is of union type.

## Self-signed containers

Let `value` be a self-signed container object. The convention is that the signature (e.g. a `"bytes96"` BLS12-381 signature) be the last field of `value`. Further, the signed message for `value` is `signing_root(value) = hash_tree_root(truncate_last(value))` where `truncate_last` truncates the last element of `value`.

## Implementations

| Language | Project | Maintainer | Implementation |
|-|-|-|-|
| Python | Ethereum 2.0 | Ethereum Foundation | [https://github.com/ethereum/py-ssz](https://github.com/ethereum/py-ssz) |
| Rust | Lighthouse | Sigma Prime | [https://github.com/sigp/lighthouse/tree/master/eth2/utils/ssz](https://github.com/sigp/lighthouse/tree/master/eth2/utils/ssz) |
| Nim | Nimbus | Status | [https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim](https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim) |
| Rust | Shasper | ParityTech | [https://github.com/paritytech/shasper/tree/master/utils/ssz](https://github.com/paritytech/shasper/tree/master/util/ssz) |
| TypeScript | Lodestar | ChainSafe Systems | [https://github.com/ChainSafe/ssz-js](https://github.com/ChainSafe/ssz-js) |
| Java | Cava | ConsenSys | [https://www.github.com/ConsenSys/cava/tree/master/ssz](https://www.github.com/ConsenSys/cava/tree/master/ssz) |
| Go | Prysm | Prysmatic Labs | [https://github.com/prysmaticlabs/go-ssz](https://github.com/prysmaticlabs/go-ssz) |
| Swift | Yeeth | Dean Eigenmann | [https://github.com/yeeth/SimpleSerialize.swift](https://github.com/yeeth/SimpleSerialize.swift) |
| C# | | Jordan Andrews | [https://github.com/codingupastorm/csharp-ssz](https://github.com/codingupastorm/csharp-ssz) |
| C++ | | Jiyun Kim | [https://github.com/NAKsir-melody/cpp_ssz](https://github.com/NAKsir-melody/cpp_ssz) |
