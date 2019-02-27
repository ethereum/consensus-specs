# [WIP] SimpleSerialiZe (SSZ)

This is a **work in progress** describing typing, serialisation and Merkleisation of Ethereum 2.0 objects.

## Table of contents

- [Constants](#constants)
- [Types](#types)
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
- [Signed containers](#signed-containers)
- [Implementations](#implementations)

## Constants

| Name | Value | Definition |
|-|:-:|-|
| `LENGTH_BYTES` | 4 | Number of bytes used for the length added before a variable-length serialized object. |

## Types

### Primitive types

* `uintN`: `N`-bit unsigned integer (where `N in [8, 16, 32, 64, 128, 256]`)
* `bool`: 1-bit unsigned integer

### Composite types

* **Containes**: ordered heterogenous collection of values
* **Tuple**: ordered fixed-size homogeneous collection of values
* **List**: ordered variable-size homogenous collection of values 

### Notation

* **Containes**: key-pair notation `{}`, e.g. `{'key1': uint64, 'key2': bool}`
* **Tuple**: angle-braket notation `[]`, e.g. `uint64[]`
* **List**: angle-braket notation `[N]`, e.g. `uint64[N]`

### Aliases

For convenience we alias:

* `byte` to `uint8`
* `bytes` to `byte[]`
* `bytesN` to `byte[N]`
* `bit` to `bool`

## Serialization

We reccursively define a `serialize` function. In the code below `value` refers to a value of the specified type.

### `uintN`

```python
assert N in [8, 16, 32, 64, 128, 256]
return value.to_bytes(N / 8, 'little')
```

### `bool`

```python
assert value in (True, False)
return b'\x01' if value is True else b'\x00'
```

### Containers

```python
serialized_elements = [serialize(element) for element in value]
serialized_bytes = reduce(lambda x, y: x + y, serialized_elements)
assert len(serialized_bytes) < 2**32
serialized_length = len(serialized_bytes).to_bytes(LENGTH_BYTES, 'little')
return serialized_length + serialized_bytes
```

### Tuples

```python
serialized_elements = [serialize(element) for element in value]
serialized_bytes = reduce(lambda x, y: x + y, serialized_elements)
return serialized_bytes
```

### Lists

```python
serialized_elements = [serialize(element) for element in value]
serialized_bytes = reduce(lambda x, y: x + y, serialized_elements)
assert len(serialized_elements) < 2**32
serialized_length = len(serialized_elements).to_bytes(LENGTH_BYTES, 'little')
return serialized_length + serialized_bytes
```

## Deserialization

Given a type, serialisation is an injective function from objects of that type to byte strings. That is, deserialisation—the inverse function—is well-defined.

## Merkleization

We first define helper functions:

* `pack`: Given ordered objects of the same basic type, serialise them, pack them into 32-byte chunks, right-pad the last chunk with zero bytes, and return the chunks.
* `merkleise`: Given ordered 32-byte chunks, right-pad them with zero chunks to the closest power of two, Merkleize the chunks, and return the root.
* `mix_in_length`: Given a Merkle root `r` and a length `l` (32-byte little-endian serialisation) return `hash(r + l)`.

Let `o` be an object. We now define object Merkleization `hash_tree_root(o)` recursively:

* `merkleize(pack(o))` if `o` is a basic object or a tuple of basic objects
* `mix_in_length(merkleize(pack(o)), len(o))` if `o` is a list of basic objects
* `merkleize([hash_tree_root(element) for element in o])` if `o` is a tuple of composite objects or a container
* `mix_in_length(merkleize([hash_tree_root(element) for element in o]), len(o))` if `o` is a list of composite objects

## Signed containers

Let `container` be a self-signed container object. The convention is that the signature (e.g. a `bytes96` BLS12-381 signature) be the last field of `container`. Further, the signed message for `container` is `signed_root(container) = hash_tree_root(truncate_last(container))` where `truncate_last` truncates the last element of `container`.

## Implementations

| Language | Implementation | Description |
|:-:|-|-|
| Python | [ https://github.com/ethereum/py-ssz ](https://github.com/ethereum/py-ssz) | Python implementation of SSZ |
| Rust | [ https://github.com/sigp/lighthouse/tree/master/beacon_chain/utils/ssz ](https://github.com/sigp/lighthouse/tree/master/beacon_chain/utils/ssz) | Lighthouse (Rust Ethereum 2.0 Node) maintained SSZ |
| Nim | [ https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim ](https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim) | Nim Implementation maintained SSZ |
| Rust | [ https://github.com/paritytech/shasper/tree/master/util/ssz ](https://github.com/paritytech/shasper/tree/master/util/ssz) | Shasper implementation of SSZ maintained by ParityTech |
| Javascript | [ https://github.com/ChainSafeSystems/ssz-js/blob/master/src/index.js ](https://github.com/ChainSafeSystems/ssz-js/blob/master/src/index.js) | Javascript Implementation maintained SSZ |
| Java | [ https://www.github.com/ConsenSys/cava/tree/master/ssz ](https://www.github.com/ConsenSys/cava/tree/master/ssz) | SSZ Java library part of the Cava suite |
| Go | [ https://github.com/prysmaticlabs/prysm/tree/master/shared/ssz ](https://github.com/prysmaticlabs/prysm/tree/master/shared/ssz) | Go implementation of SSZ mantained by Prysmatic Labs |
| Swift | [ https://github.com/yeeth/SimpleSerialize.swift ](https://github.com/yeeth/SimpleSerialize.swift) | Swift implementation maintained SSZ |
| C# | [ https://github.com/codingupastorm/csharp-ssz ](https://github.com/codingupastorm/csharp-ssz) | C# implementation maintained SSZ |
| C++ | [ https://github.com/NAKsir-melody/cpp_ssz](https://github.com/NAKsir-melody/cpp_ssz) | C++ implementation maintained SSZ |
