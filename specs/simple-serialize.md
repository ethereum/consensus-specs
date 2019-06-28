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
        - [Aliases](#aliases)
        - [Default values](#default-values)
        - [Illegal types](#illegal-types)
    - [Serialization](#serialization)
        - [`uintN`](#uintn)
        - [`boolean`](#boolean)
        - [`null`](#null)
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
* `null`: `{}`, i.e. the empty container

### Default values

The default value of a type upon initialization is recursively defined using `0` for `uintN`, `False` for `boolean` and the elements of `Bitvector`, and `[]` for lists and `Bitlist`. Unions default to the first type in the union (with type index zero), which is `null` if present in the union.

#### `is_empty`

An SSZ object is called empty (and thus, `is_empty(object)` returns true) if it is equal to the default value for that type.

### Illegal types

Empty vector types (i.e. `[subtype, 0]` for some `subtype`) are not legal. The `null` type is only legal as the first type in a union subtype (i.e. with type index zero).

## Serialization

We recursively define the `serialize` function which consumes an object `value` (of the type specified) and returns a bytestring of type `bytes`.

*Note*: In the function definitions below (`serialize`, `hash_tree_root`, `signing_root`, `is_variable_size`, etc.) objects implicitly carry their type.

### `uintN`

```python
assert N in [8, 16, 32, 64, 128, 256]
return value.to_bytes(N // 8, "little")
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
as_integer = sum([value[i] << i for i in range(len(value))])
return as_integer.to_bytes((N + 7) // 8, "little")
```

### `Bitlist[N]`

Note that from the offset coding, the length (in bytes) of the bitlist is known. An additional leading `1` bit is added so that the length in bits will also be known.

```python
as_integer = (1 << len(value)) + sum([value[i] << i for i in range(len(value))])
return as_integer.to_bytes((as_integer.bit_length() + 7) // 8, "little")
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
- Offsets: out of order, out of range, mismatching minimum element size
- Scope: Extra unused bytes, not aligned with element size.
- More elements than a list limit allows. Part of enforcing consensus.

## Merkleization

We first define helper functions:

* `pack`: Given ordered objects of the same basic type, serialize them, pack them into `BYTES_PER_CHUNK`-byte chunks, right-pad the last chunk with zero bytes, and return the chunks.
* `next_pow_of_two(i)`: get the next power of 2 of `i`, if not already a power of 2, with 0 mapping to 1. Examples: `0->1, 1->1, 2->2, 3->4, 4->4, 6->8, 9->16`
* `merkleize(data, pad_for)`: Given ordered `BYTES_PER_CHUNK`-byte chunks, if necessary append zero chunks so that the number of chunks is a power of two, Merkleize the chunks, and return the root.
  The merkleization depends on the effective input, which can be padded: if `pad_for=L`, then pad the `data` with zeroed chunks to `next_pow_of_two(L)` (virtually for memory efficiency).
  Then, merkleize the chunks (empty input is padded to 1 zero chunk):
    - If `1` chunk: A single chunk is simply that chunk, i.e. the identity when the number of chunks is one.
    - If `> 1` chunks: pad to `next_pow_of_two(len(chunks))`, merkleize as binary tree.
* `mix_in_length`: Given a Merkle root `root` and a length `length` (`"uint256"` little-endian serialization) return `hash(root + length)`.
* `mix_in_type`: Given a Merkle root `root` and a type_index `type_index` (`"uint256"` little-endian serialization) return `hash(root + type_index)`.

We now define Merkleization `hash_tree_root(value)` of an object `value` recursively:

* `merkleize(pack(value))` if `value` is a basic object or a vector of basic objects
* `mix_in_length(merkleize(pack(value), pad_for=(N * elem_size / BYTES_PER_CHUNK)), len(value))` if `value` is a list of basic objects.
* `merkleize([hash_tree_root(element) for element in value])` if `value` is a vector of composite objects or a container
* `mix_in_length(merkleize([hash_tree_root(element) for element in value], pad_for=N), len(value))` if `value` is a list of composite objects.
* `mix_in_type(merkleize(value.value), value.type_index)` if `value` is of union type

### Merkleization of `Bitvector[N]`

```python
as_integer = sum([value[i] << i for i in range(len(value))])
return merkleize(as_integer.to_bytes((N + 7) // 8, "little"))
```

### `Bitlist[N]`

```python
as_integer = sum([value[i] << i for i in range(len(value))])
return mix_in_length(merkleize(as_integer.to_bytes((N + 7) // 8, "little")), len(value))
```

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
