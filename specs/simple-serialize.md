# SimpleSerialiZe (SSZ)

This is a **work in progress** describing typing, serialization and Merkleization of Ethereum 2.0 objects.

## Table of contents

- [Constants](#constants)
- [Typing](#typing)
    - [Basic types](#basic-types)
    - [Composite types](#composite-types)
    - [Aliases](#aliases)
- [Serialization](#serialization)
    - [`uintN`](#uintn)
    - [`bool`](#bool)
    - [Tuples, containers, lists](#tuples-containers-lists)
- [Deserialization](#deserialization)
- [Merkleization](#merkleization)
- [Self-signed containers](#self-signed-containers)
- [Implementations](#implementations)

## Constants

| Name | Value | Description |
|-|-|-|
| `BYTES_PER_CHUNK` | `32` | Number of bytes per chunk.
| `BYTES_PER_LENGTH_PREFIX` | `4` | Number of bytes per serialized length prefix. |

## Typing
### Basic types

* `uintN`: `N`-bit unsigned integer (where `N in [8, 16, 32, 64, 128, 256]`)
* `bool`: `True` or `False`

### Composite types

* **container**: ordered heterogenous collection of values
    * key-pair curly bracket notation `{}`, e.g. `{'foo': "uint64", 'bar': "bool"}`
* **tuple**: ordered fixed-length homogeneous collection of values
    * angle bracket notation `[N]`, e.g. `uint64[N]`
* **list**: ordered variable-length homogenous collection of values
    * angle bracket notation `[]`, e.g. `uint64[]`

### Aliases

For convenience we alias:

* `byte` to `uint8` (this is a basic type)
* `bytes` to `byte[]` (this is *not* a basic type)
* `bytesN` to `byte[N]` (this is *not* a basic type)

## Serialization

We recursively define the `serialize` function which consumes an object `value` (of the type specified) and returns a bytestring of type `bytes`.

*Note*: In the function definitions below (`serialize`, `hash_tree_root`, `signed_root`, etc.) objects implicitly carry their type.

### `uintN`

```python
assert N in [8, 16, 32, 64, 128, 256]
return value.to_bytes(N // 8, 'little')
```

### `bool`

```python
assert value in (True, False)
return b'\x01' if value is True else b'\x00'
```

### Tuples, containers, lists

If `value` is fixed-length (i.e. does not embed a list):

```python
return ''.join([serialize(element) for element in value])
```

If `value` is variable-length (i.e. embeds a list):

```python
serialized_bytes = ''.join([serialize(element) for element in value])
assert len(serialized_bytes) < 2**(8 * BYTES_PER_LENGTH_PREFIX)
serialized_length = len(serialized_bytes).to_bytes(BYTES_PER_LENGTH_PREFIX, 'little')
return serialized_length + serialized_bytes
```

## Deserialization

Because serialization is an injective function (i.e. two distinct objects of the same type will serialize to different values) any bytestring has at most one object it could deserialize to. Efficient algorithms for computing this object can be found in [the implementations](#implementations).

## Merkleization

We first define helper functions:

* `pack`: Given ordered objects of the same basic type, serialize them, pack them into `BYTES_PER_CHUNK`-byte chunks, right-pad the last chunk with zero bytes, and return the chunks.
* `merkleize`: Given ordered `BYTES_PER_CHUNK`-byte chunks, if necessary append zero chunks so that the number of chunks is a power of two, Merkleize the chunks, and return the root.
* `mix_in_length`: Given a Merkle root `root` and a length `length` (`uint256` little-endian serialization) return `hash(root + length)`.

We now define Merkleization `hash_tree_root(value)` of an object `value` recursively:

* `merkleize(pack(value))` if `value` is a basic object or a tuple of basic objects
* `mix_in_length(merkleize(pack(value)), len(value))` if `value` is a list of basic objects
* `merkleize([hash_tree_root(element) for element in value])` if `value` is a tuple of composite objects or a container
* `mix_in_length(merkleize([hash_tree_root(element) for element in value]), len(value))` if `value` is a list of composite objects

## Self-signed containers

Let `value` be a self-signed container object. The convention is that the signature (e.g. a `bytes96` BLS12-381 signature) be the last field of `value`. Further, the signed message for `value` is `signed_root(value) = hash_tree_root(truncate_last(value))` where `truncate_last` truncates the last element of `value`.

## Implementations

| Language | Project | Maintainer | Implementation |
|-|-|-|-|
| Python | Ethereum 2.0 | Ethereum Foundation | [https://github.com/ethereum/py-ssz](https://github.com/ethereum/py-ssz) |
| Rust | Lighthouse | Sigma Prime | [https://github.com/sigp/lighthouse/tree/master/beacon_chain/utils/ssz](https://github.com/sigp/lighthouse/tree/master/beacon_chain/utils/ssz) |
| Nim | Nimbus | Status | [https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim](https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim) |
| Rust | Shasper | ParityTech | [https://github.com/paritytech/shasper/tree/master/util/ssz](https://github.com/paritytech/shasper/tree/master/util/ssz) |
| Javascript | Lodestart | Chain Safe Systems | [https://github.com/ChainSafeSystems/ssz-js/blob/master/src/index.js](https://github.com/ChainSafeSystems/ssz-js/blob/master/src/index.js) |
| Java | Cava | ConsenSys | [https://www.github.com/ConsenSys/cava/tree/master/ssz](https://www.github.com/ConsenSys/cava/tree/master/ssz) |
| Go | Prysm | Prysmatic Labs | [https://github.com/prysmaticlabs/prysm/tree/master/shared/ssz](https://github.com/prysmaticlabs/prysm/tree/master/shared/ssz) |
| Swift | Yeeth | Dean Eigenmann | [https://github.com/yeeth/SimpleSerialize.swift](https://github.com/yeeth/SimpleSerialize.swift) |
| C# | | Jordan Andrews | [https://github.com/codingupastorm/csharp-ssz](https://github.com/codingupastorm/csharp-ssz) |
| C++ | | | [https://github.com/NAKsir-melody/cpp_ssz](https://github.com/NAKsir-melody/cpp_ssz) |
