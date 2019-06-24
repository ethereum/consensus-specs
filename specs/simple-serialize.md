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
        - [`"uintN"`](#uintn)
        - [`"bool"`](#bool)
        - [`"null`](#null)
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

* `"uintN"`: `N`-bit unsigned integer (where `N in [8, 16, 32, 64, 128, 256]`)
* `"bool"`: `True` or `False`

### Composite types

* **container**: ordered heterogeneous collection of values
    * key-pair curly bracket notation `{}`, e.g. `{"foo": "uint64", "bar": "bool"}`
* **vector**: ordered fixed-length homogeneous collection of values
    * angle bracket notation `[type, N]`, e.g. `["uint64", N]`
* **list**: ordered variable-length homogeneous collection of values
    * angle bracket notation `[type]`, e.g. `["uint64"]`
* **union**: union type containing one of the given subtypes
    * round bracket notation `(type_1, type_2, ...)`, e.g. `("null", "uint64")`

### Variable-size and fixed-size

We recursively define "variable-size" types to be lists and unions and all types that contain a variable-size type. All other types are said to be "fixed-size".

### Aliases

For convenience we alias:

* `"byte"` to `"uint8"` (this is a basic type)
* `"bytes"` to `["byte"]` (this is *not* a basic type)
* `"bytesN"` to `["byte", N]` (this is *not* a basic type)
* `"null"`: `{}`, i.e. the empty container

### Default values

The default value of a type upon initialization is recursively defined using `0` for `"uintN"`, `False` for `"bool"`, and `[]` for lists. Unions default to the first type in the union (with type index zero), which is `"null"` if present in the union.

#### `is_empty`

An SSZ object is called empty (and thus, `is_empty(object)` returns true) if it is equal to the default value for that type.

### Illegal types

Empty vector types (i.e. `[subtype, 0]` for some `subtype`) are not legal. The `"null"` type is only legal as the first type in a union subtype (i.e. with type index zero).

## Serialization

We recursively define the `serialize` function which consumes an object `value` (of the type specified) and returns a bytestring of type `"bytes"`.

*Note*: In the function definitions below (`serialize`, `hash_tree_root`, `signing_root`, `is_variable_size`, etc.) objects implicitly carry their type.

### `"uintN"`

```python
assert N in [8, 16, 32, 64, 128, 256]
return value.to_bytes(N // 8, "little")
```

### `"bool"`

```python
assert value in (True, False)
return b"\x01" if value is True else b"\x00"
```

### `"null"`

```python
return b""
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

## Merkleization

We first define helper functions:

* `pack`: Given ordered objects of the same basic type, serialize them, pack them into `BYTES_PER_CHUNK`-byte chunks, right-pad the last chunk with zero bytes, and return the chunks.
* `merkleize`: Given ordered `BYTES_PER_CHUNK`-byte chunks, if necessary append zero chunks so that the number of chunks is a power of two, Merkleize the chunks, and return the root. Note that `merkleize` on a single chunk is simply that chunk, i.e. the identity when the number of chunks is one.
* `mix_in_length`: Given a Merkle root `root` and a length `length` (`"uint256"` little-endian serialization) return `hash(root + length)`.
* `mix_in_type`: Given a Merkle root `root` and a type_index `type_index` (`"uint256"` little-endian serialization) return `hash(root + type_index)`.

We now define Merkleization `hash_tree_root(value)` of an object `value` recursively:

* `merkleize(pack(value))` if `value` is a basic object or a vector of basic objects
* `mix_in_length(merkleize(pack(value)), len(value))` if `value` is a list of basic objects
* `merkleize([hash_tree_root(element) for element in value])` if `value` is a vector of composite objects or a container
* `mix_in_length(merkleize([hash_tree_root(element) for element in value]), len(value))` if `value` is a list of composite objects
* `mix_in_type(merkleize(value.value), value.type_index)` if `value` is of union type

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
