# SimpleSerialiZe (SSZ)

This is a **work in progress** describing typing, serialization and Merkleization of Ethereum 2.0 objects.

## Table of contents

- [Constants](#constants)
- [Typing](#typing)
    - [Primitive types](#primitive-types)
    - [Composite types](#composite-types)
    - [Notation](#notation)
    - [Aliases](#aliases)
- [Serialization](#serialization)
    - [`uintN`](#uintn)
    - [`bool`](#bool)
    - [Containers](#containers)
    - [Tuples](#tuples)
    - [Lists](#lists)
- [Deserialization](#deserialization)
- [Merkleization](#merkleization)
- [Self-signed containers](#self-signed-containers)
- [Implementations](#implementations)

## Constants

| Name | Value | Description |
|-|-|-|
| `LENGTH_BYTES` | `4` | Number of bytes for the length of variable-length serialized objects. |
| `MAX_LENGTH` | `2**(8 * LENGTH_BYTES)` | Maximum serialization length. |

## Typing

### Primitive types

* `uintN`: `N`-bit unsigned integer (where `N in [8, 16, 32, 64, 128, 256]`)
* `bool`: 1-bit unsigned integer

### Composite types

* **Container**: ordered heterogenous collection of values
* **Tuple**: ordered fixed-length homogeneous collection of values
* **List**: ordered variable-length homogenous collection of values 

### Notation

* **Container**: key-pair curly braken notation `{}` (e.g. `{'key1': uint64, 'key2': bool}`)
* **Tuple**: angle braket notation `[N]` (e.g. `uint64[N]`)
* **List**: angle braket notation `[]` (e.g. `uint64[]`)

### Aliases

For convenience we alias:

* `byte` to `uint8`
* `bytes` to `byte[]`
* `bytesN` to `byte[N]`
* `bit` to `bool`

## Serialization

We reccursively define the `serialize` function which consumes an object `object` (of the type specified) and returns a byte string of type `bytes`.

### `uintN`

```python
assert N in [8, 16, 32, 64, 128, 256]
return object.to_bytes(N / 8, 'little')
```

### `bool`

```python
assert object in (True, False)
return b'\x01' if object is True else b'\x00'
```

### Containers

```python
serialized_elements = [serialize(element) for element in object]
serialized_bytes = reduce(lambda x, y: x + y, serialized_elements)
assert len(serialized_bytes) < MAX_LENGTH
serialized_length = len(serialized_bytes).to_bytes(LENGTH_BYTES, 'little')
return serialized_length + serialized_bytes
```

### Tuples

```python
serialized_elements = [serialize(element) for element in object]
serialized_bytes = reduce(lambda x, y: x + y, serialized_elements)
return serialized_bytes
```

### Lists

```python
serialized_elements = [serialize(element) for element in object]
serialized_bytes = reduce(lambda x, y: x + y, serialized_elements)
assert len(serialized_elements) < MAX_LENGTH
serialized_length = len(serialized_elements).to_bytes(LENGTH_BYTES, 'little')
return serialized_length + serialized_bytes
```

## Deserialization

Given a type, serialization is an injective function from objects of that type to byte strings. That is, deserialization—the inverse function—is well-defined.

## Merkleization

We first define helper functions:

* `pack`: Given ordered objects of the same basic type, serialize them, pack them into 32-byte chunks, right-pad the last chunk with zero bytes, and return the chunks.
* `merkleize`: Given ordered 32-byte chunks, right-pad them with zero chunks to the closest power of two, Merkleize the chunks, and return the root.
* `mix_in_length`: Given a Merkle root `root` and a length `length` (32-byte little-endian serialization) return `hash(root + length)`.

Let `object` be an object. We now define object Merkleization `hash_tree_root(object)` recursively:

* `merkleize(pack(object))` if `object` is a basic object or a tuple of basic objects
* `mix_in_length(merkleize(pack(object)), len(object))` if `object` is a list of basic objects
* `merkleize([hash_tree_root(element) for element in object])` if `object` is a tuple of composite objects or a container
* `mix_in_length(merkleize([hash_tree_root(element) for element in object]), len(object))` if `object` is a list of composite objects

## Self-signed containers

Let `container` be a self-signed container object. The convention is that the signature (e.g. a `bytes96` BLS12-381 signature) be the last field of `container`. Further, the signed message for `container` is `signed_root(container) = hash_tree_root(truncate_last(container))` where `truncate_last` truncates the last element of `container`.

## Implementations

| Language | Project | Maintainer | Implementation |
|:-:|-|-|
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
