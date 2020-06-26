# SimpleSerialize (SSZ)

**Notice**: This document is a work-in-progress describing typing, serialization, and Merkleization of Eth2 objects.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Constants](#constants)
- [Typing](#typing)
  - [Basic types](#basic-types)
  - [Composite types](#composite-types)
  - [Variable-size and fixed-size](#variable-size-and-fixed-size)
  - [Aliases](#aliases)
  - [Default values](#default-values)
    - [`is_zero`](#is_zero)
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
- [Summaries and expansions](#summaries-and-expansions)
- [Implementations](#implementations)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
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
    * notation `Union[type_0, type_1, ...]`, e.g. `union[null, uint64]`

*Note*: Both `Vector[boolean, N]` and `Bitvector[N]` are valid, yet distinct due to their different serialization requirements. Similarly, both `List[boolean, N]` and `Bitlist[N]` are valid, yet distinct. Generally `Bitvector[N]`/`Bitlist[N]` are preferred because of their serialization efficiencies.

### Variable-size and fixed-size

We recursively define "variable-size" types to be lists, unions, `Bitlist` and all types that contain a variable-size type. All other types are said to be "fixed-size".

### Aliases

For convenience we alias:

* `bit` to `boolean`
* `byte` to `uint8` (this is a basic type)
* `BytesN` to `Vector[byte, N]` (this is *not* a basic type)
* `null`: `{}`

### Default values
Assuming a helper function `default(type)` which returns the default value for `type`, we can recursively define the default value for all types.

| Type | Default Value |
| ---- | ------------- |
| `uintN` | `0` |
| `boolean` | `False` |
| `Container` | `[default(type) for type in container]` |
| `Vector[type, N]` | `[default(type)] * N` |
| `Bitvector[N]` | `[False] * N` |
| `List[type, N]` | `[]` |
| `Bitlist[N]` | `[]` |
| `Union[type_0, type_1, ...]` | `default(type_0)` |

#### `is_zero`

An SSZ object is called zeroed (and thus, `is_zero(object)` returns true) if it is equal to the default value for that type.

### Illegal types

- Empty vector types (`Vector[type, 0]`, `Bitvector[0]`) are illegal.
- Containers with no fields are illegal.
- The `null` type is only legal as the first type in a union subtype (i.e. with type index zero).

## Serialization

We recursively define the `serialize` function which consumes an object `value` (of the type specified) and returns a bytestring of type `bytes`.

*Note*: In the function definitions below (`serialize`, `hash_tree_root`, `is_variable_size`, etc.) objects implicitly carry their type.

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

Note that from the offset coding, the length (in bytes) of the bitlist is known. An additional `1` bit is added to the end, at index `e` where `e` is the length of the bitlist (not the limit), so that the length in bits will also be known.

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

Because serialization is an injective function (i.e. two distinct objects of the same type will serialize to different values) any bytestring has at most one object it could deserialize to. 

Deserialization can be implemented using a recursive algorithm. The deserialization of basic objects is easy, and from there we can find a simple recursive algorithm for all fixed-size objects. For variable-size objects we have to do one of the following depending on what kind of object it is:

* Vector/list of a variable-size object: The serialized data will start with offsets of all the serialized objects (`BYTES_PER_LENGTH_OFFSET` bytes each).
  * Using the first offset, we can compute the length of the list (divide by `BYTES_PER_LENGTH_OFFSET`), as it gives us the total number of bytes in the offset data.
  * The size of each object in the vector/list can be inferred from the difference of two offsets. To get the size of the last object, the total number of bytes has to be known (it is not generally possible to deserialize an SSZ object of unknown length)
* Containers follow the same principles as vectors, with the difference that there may be fixed-size objects in a container as well. This means the `fixed_parts` data will contain offsets as well as fixed-size objects.
* In the case of bitlists, the length in bits cannot be uniquely inferred from the number of bytes in the object. Because of this, they have a bit at the end that is always set. This bit has to be used to infer the size of the bitlist in bits.

Note that deserialization requires hardening against invalid inputs. A non-exhaustive list:

- Offsets: out of order, out of range, mismatching minimum element size.
- Scope: Extra unused bytes, not aligned with element size.
- More elements than a list limit allows. Part of enforcing consensus.

Efficient algorithms for computing this object can be found in [the implementations](#implementations).

## Merkleization

We first define helper functions:

* `size_of(B)`, where `B` is a basic type: the length, in bytes, of the serialized form of the basic type.
* `chunk_count(type)`: calculate the amount of leafs for merkleization of the type.
   * all basic types: `1`
   * `Bitlist[N]` and `Bitvector[N]`: `(N + 255) // 256` (dividing by chunk size, rounding up)
   * `List[B, N]` and `Vector[B, N]`, where `B` is a basic type: `(N * size_of(B) + 31) // 32` (dividing by chunk size, rounding up)
   * `List[C, N]` and `Vector[C, N]`, where `C` is a composite type: `N`
   * containers: `len(fields)`
* `pack(values)`: Given ordered objects of the same basic type:
   1. Serialize `values` into bytes.
   2. If not aligned to a multiple of `BYTES_PER_CHUNK` bytes, right-pad with zeroes to the next multiple.
   3. Partition the bytes into `BYTES_PER_CHUNK`-byte chunks.
   4. Return the chunks.
* `pack_bits(bits)`: Given the bits of bitlist or bitvector, get `bitfield_bytes` by packing them in bytes and aligning to the start. The length-delimiting bit for bitlists is excluded. Then return `pack(bitfield_bytes)`.
* `next_pow_of_two(i)`: get the next power of 2 of `i`, if not already a power of 2, with 0 mapping to 1. Examples: `0->1, 1->1, 2->2, 3->4, 4->4, 6->8, 9->16`
* `merkleize(chunks, limit=None)`: Given ordered `BYTES_PER_CHUNK`-byte chunks, merkleize the chunks, and return the root:
    * The merkleization depends on the effective input, which must be padded/limited:
        - if no limit: pad the `chunks` with zeroed chunks to `next_pow_of_two(len(chunks))` (virtually for memory efficiency).
        - if `limit >= len(chunks)`, pad the `chunks` with zeroed chunks to `next_pow_of_two(limit)` (virtually for memory efficiency).
        - if `limit < len(chunks)`: do not merkleize, input exceeds limit. Raise an error instead.
    * Then, merkleize the chunks (empty input is padded to 1 zero chunk):
        - If `1` chunk: the root is the chunk itself.
        - If `> 1` chunks: merkleize as binary tree.
* `mix_in_length`: Given a Merkle root `root` and a length `length` (`"uint256"` little-endian serialization) return `hash(root + length)`.
* `mix_in_type`: Given a Merkle root `root` and a type_index `type_index` (`"uint256"` little-endian serialization) return `hash(root + type_index)`.

We now define Merkleization `hash_tree_root(value)` of an object `value` recursively:

* `merkleize(pack(value))` if `value` is a basic object or a vector of basic objects.
* `merkleize(pack_bits(value), limit=chunk_count(type))` if `value` is a bitvector.
* `mix_in_length(merkleize(pack(value), limit=chunk_count(type)), len(value))` if `value` is a list of basic objects.
* `mix_in_length(merkleize(pack_bits(value), limit=chunk_count(type)), len(value))` if `value` is a bitlist.
* `merkleize([hash_tree_root(element) for element in value])` if `value` is a vector of composite objects or a container.
* `mix_in_length(merkleize([hash_tree_root(element) for element in value], limit=chunk_count(type)), len(value))` if `value` is a list of composite objects.
* `mix_in_type(merkleize(value.value), value.type_index)` if `value` is of union type.

## Summaries and expansions

Let `A` be an object derived from another object `B` by replacing some of the (possibly nested) values of `B` by their `hash_tree_root`. We say `A` is a "summary" of `B`, and that `B` is an "expansion" of `A`. Notice `hash_tree_root(A) == hash_tree_root(B)`.

We similarly define "summary types" and "expansion types". For example, [`BeaconBlock`](../specs/phase0/beacon-chain.md#beaconblock) is an expansion type of [`BeaconBlockHeader`](../specs/phase0/beacon-chain.md#beaconblockheader). Notice that objects expand to at most one object of a given expansion type. For example, `BeaconBlockHeader` objects uniquely expand to `BeaconBlock` objects.

## Implementations

| Language | Project | Maintainer | Implementation |
|-|-|-|-|
| Python | Ethereum 2.0 | Ethereum Foundation | [https://github.com/ethereum/py-ssz](https://github.com/ethereum/py-ssz) |
| Rust | Lighthouse | Sigma Prime | [https://github.com/sigp/lighthouse/tree/master/eth2/utils/ssz](https://github.com/sigp/lighthouse/tree/master/eth2/utils/ssz) |
| Nim | Nimbus | Status | [https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim](https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim) |
| Rust | Shasper | ParityTech | [https://github.com/paritytech/shasper/tree/master/utils/ssz](https://github.com/paritytech/shasper/tree/master/utils/ssz) |
| TypeScript | Lodestar | ChainSafe Systems | [https://github.com/ChainSafe/ssz-js](https://github.com/ChainSafe/ssz) |
| Java | Cava | ConsenSys | [https://www.github.com/ConsenSys/cava/tree/master/ssz](https://www.github.com/ConsenSys/cava/tree/master/ssz) |
| Go | Prysm | Prysmatic Labs | [https://github.com/prysmaticlabs/go-ssz](https://github.com/prysmaticlabs/go-ssz) |
| Swift | Yeeth | Dean Eigenmann | [https://github.com/yeeth/SimpleSerialize.swift](https://github.com/yeeth/SimpleSerialize.swift) |
| C# | | Jordan Andrews | [https://github.com/codingupastorm/csharp-ssz](https://github.com/codingupastorm/csharp-ssz) |
| C# | Cortex | Sly Gryphon | [https://www.nuget.org/packages/Cortex.SimpleSerialize](https://www.nuget.org/packages/Cortex.SimpleSerialize) |
| C++ | | Jiyun Kim | [https://github.com/NAKsir-melody/cpp_ssz](https://github.com/NAKsir-melody/cpp_ssz) |
