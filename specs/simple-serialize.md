# [WIP] SimpleSerialize (SSZ) Spec

This is the **work in progress** document to describe `SimpleSerialize`, the
current selected serialization method for Ethereum 2.0 using the Beacon Chain.

This document specifies the general information for serializing and
deserializing objects and data types.

## ToC

* [About](#about)
* [Variables and Functions](#variables-and-functions)
* [Constants](#constants)
* [Overview](#overview)
   + [Serialize/Encode](#serializeencode)
      - [uintN](#uintn)
      - [bool](#bool)
      - [bytesN](#bytesn)
      - [List/Vectors](#listvectors)
      - [Container](#container)
   + [Deserialize/Decode](#deserializedecode)
      - [uintN](#uintn-1)
      - [bool](#bool-1)
      - [bytesN](#bytesn-1)
      - [List/Vectors](#listvectors-1)
      - [Container](#container-1)
   + [Tree Hash](#tree-hash)
      - [`uint8`..`uint256`, `bool`, `bytes1`..`bytes32`](#uint8uint256-bool-bytes1bytes32)
      - [`uint264`..`uintN`, `bytes33`..`bytesN`](#uint264uintn-bytes33bytesn)
      - [List/Vectors](#listvectors-2)
      - [Container](#container-2)
   + [Signed Roots](#signed-roots)
* [Implementations](#implementations)

## About

`SimpleSerialize` was first proposed by Vitalik Buterin as the serialization
protocol for use in the Ethereum 2.0 Beacon Chain.

The core feature of `ssz` is the simplicity of the serialization with low
overhead.

## Variables and Functions

| Term         | Definition                                                                                     |
|:-------------|:-----------------------------------------------------------------------------------------------|
| `little`     | Little endian.                                                                                 |
| `byteorder`  | Specifies [endianness](https://en.wikipedia.org/wiki/Endianness): big endian or little endian. |
| `len`        | Length/number of bytes.                                                                        |
| `to_bytes`   | Convert to bytes. Should take parameters ``size`` and ``byteorder``.                           |
| `from_bytes` | Convert from bytes to object. Should take ``bytes`` and ``byteorder``.                         |
| `value`      | The value to serialize.                                                                        |
| `rawbytes`   | Raw serialized bytes.                                                                          |
| `deserialized_object` | The deserialized data in the data structure of your programming language.             |
| `new_index`  | An index to keep track the latest position where the `rawbytes` have been deserialized.        |

## Constants

| Constant          | Value | Definition                                                                            |
|:------------------|:-----:|:--------------------------------------------------------------------------------------|
| `LENGTH_BYTES`    |   4   | Number of bytes used for the length added before a variable-length serialized object. |
| `SSZ_CHUNK_SIZE`  |  128  | Number of bytes for the chunk size of the Merkle tree leaf.                           |

## Overview

### Serialize/Encode

#### uintN

| uint Type | Usage                                                      |
|:---------:|:-----------------------------------------------------------|
| `uintN`   | Type of `N` bits unsigned integer, where ``N % 8 == 0``.   |

Convert directly to bytes the size of the int. (e.g. ``uint16 = 2 bytes``)

All integers are serialized as **little endian**.

| Check to perform       | Code                  |
|:-----------------------|:----------------------|
| Size is a byte integer | ``int_size % 8 == 0`` |

```python
assert(int_size % 8 == 0)
buffer_size = int_size / 8
return value.to_bytes(buffer_size, 'little')
```

#### bool

Convert directly to a single 0x00 or 0x01 byte.

| Check to perform  | Code                       |
|:------------------|:---------------------------|
| Value is boolean  | ``value in (True, False)`` |

```python
assert(value in (True, False))
return b'\x01' if value is True else b'\x00'
```

#### bytesN

A fixed-size byte array.

| Checks to perform                      | Code                 |
|:---------------------------------------|:---------------------|
| Length in bytes is correct for `bytesN` | ``len(value) == N`` |

```python
assert(len(value) == N)

return value
```

#### List/Vectors

Lists are a collection of elements of the same homogeneous type.

| Check to perform                            | Code                        |
|:--------------------------------------------|:----------------------------|
| Length of serialized list fits into 4 bytes | ``len(serialized) < 2**32`` |

1. Serialize all list elements individually and concatenate them.
2. Prefix the concatenation with its length encoded as a `4-byte` **little-endian** unsigned integer.

We define `bytes` to be a synonym of `List[bytes1]`.

**Example in Python**

```python

serialized_list_string = b''

for item in value:
   serialized_list_string += serialize(item)

assert(len(serialized_list_string) < 2**32)

serialized_len = (len(serialized_list_string).to_bytes(LENGTH_BYTES, 'little'))

return serialized_len + serialized_list_string
```

#### Container

A container represents a heterogenous, associative collection of key-value pairs. Each pair is referred to as a `field`. To get the value for a given field, you supply the key which is a symbol unique to the container referred to as the field's `name`. The container data type is analogous to the `struct` type found in many languages like C or Go.

To serialize a container, obtain the list of its field's names in the specified order. For each field name in this list, obtain the corresponding value and serialize it. Tightly pack the complete set of serialized values in the same order as the field names into a buffer. Calculate the size of this buffer of serialized bytes and encode as a `4-byte` **little endian** `uint32`. Prepend the encoded length to the buffer. The result of this concatenation is the final serialized value of the container.

| Check to perform                              | Code                        |
|:----------------------------------------------|:----------------------------|
| Length of serialized fields fits into 4 bytes | ``len(serialized) < 2**32`` |

To serialize:

1. Get the list of the container's fields.

2. For each name in the list, obtain the corresponding value from the container and serialize it. Place this serialized value into a buffer. The serialized values should be tightly packed.

3. Get the number of raw bytes in the serialized buffer. Encode that number as a `4-byte` **little endian** `uint32`.

4. Prepend the length to the serialized buffer.

**Example in Python**

```python
def get_field_names(typ):
    return typ.fields.keys()

def get_value_for_field_name(value, field_name):
    return getattr(value, field_name)

def get_type_for_field_name(typ, field_name):
    return typ.fields[field_name]

serialized_buffer = b''

typ = type(value)
for field_name in get_field_names(typ):
    field_value = get_value_for_field_name(value, field_name)
    field_type = get_type_for_field_name(typ, field_name)
    serialized_buffer += serialize(field_value, field_type)

assert(len(serialized_buffer) < 2**32)

serialized_len = (len(serialized_buffer).to_bytes(LENGTH_BYTES, 'little'))

return serialized_len + serialized_buffer
```

### Deserialize/Decode

The decoding requires knowledge of the type of the item to be decoded. When
performing decoding on an entire serialized string, it also requires knowledge
of the order in which the objects have been serialized.

Note: Each return will provide:
- `deserialized_object`
- `new_index`

At each step, the following checks should be made:

| Check to perform         | Check                                                      |
|:-------------------------|:-----------------------------------------------------------|
| Ensure sufficient length | ``len(rawbytes) >= current_index + deserialize_length``    |

At the final step, the following checks should be made:

| Check to perform         | Check                                |
|:-------------------------|:-------------------------------------|
| Ensure no extra length   | `new_index == len(rawbytes)`         |

#### uintN

Convert directly from bytes into integer utilising the number of bytes the same
size as the integer length. (e.g. ``uint16 == 2 bytes``)

All integers are interpreted as **little endian**.

```python
byte_length = int_size / 8
new_index = current_index + byte_length
assert(len(rawbytes) >= new_index)
return int.from_bytes(rawbytes[current_index:current_index+byte_length], 'little'), new_index
```

#### bool

Return True if 0x01, False if 0x00.

```python
assert rawbytes in (b'\x00', b'\x01')
return True if rawbytes == b'\x01' else False
```

#### bytesN

Return the `N` bytes.

```python
assert(len(rawbytes) >= current_index + N)
new_index = current_index + N
return rawbytes[current_index:current_index+N], new_index
```

#### List/Vectors

Deserialize each element in the list.
1. Get the length of the serialized list.
2. Loop through deserializing each item in the list until you reach the
entire length of the list.

| Check to perform                          | code                                                            |
|:------------------------------------------|:----------------------------------------------------------------|
| ``rawbytes`` has enough left for length   | ``len(rawbytes) > current_index + LENGTH_BYTES``                |
| list is not greater than serialized bytes | ``len(rawbytes) > current_index + LENGTH_BYTES + total_length`` |

```python
assert(len(rawbytes) > current_index + LENGTH_BYTES)
total_length = int.from_bytes(rawbytes[current_index:current_index + LENGTH_BYTES], 'little')
new_index = current_index + LENGTH_BYTES + total_length
assert(len(rawbytes) >= new_index)
item_index = current_index + LENGTH_BYTES
deserialized_list = []

while item_index < new_index:
   object, item_index = deserialize(rawbytes, item_index, item_type)
   deserialized_list.append(object)

return deserialized_list, new_index
```

#### Container

Refer to the section on container encoding for some definitions.

To deserialize a container, loop over each field in the container and use the type of that field to know what kind of deserialization to perform. Consume successive elements of the data stream for each successful deserialization.

Instantiate a container with the full set of deserialized data, matching each member with the corresponding field.

| Check to perform                          | code                                                            |
|:------------------------------------------|:----------------------------------------------------------------|
| ``rawbytes`` has enough left for length   | ``len(rawbytes) > current_index + LENGTH_BYTES``                |
| list is not greater than serialized bytes | ``len(rawbytes) > current_index + LENGTH_BYTES + total_length`` |

To deserialize:

1. Get the list of the container's fields.
2. For each name in the list, attempt to deserialize a value for that type. Collect these values as they will be used to construct an instance of the container.
3. Construct a container instance after successfully consuming the entire subset of the stream for the serialized container.

**Example in Python**

```python
def get_field_names(typ):
    return typ.fields.keys()

def get_value_for_field_name(value, field_name):
    return getattr(value, field_name)

def get_type_for_field_name(typ, field_name):
    return typ.fields[field_name]

class Container:
    # this is the container; here we will define an empty class for demonstration
    pass

# get a reference to the type in some way...
container = Container()
typ = type(container)

assert(len(rawbytes) > current_index + LENGTH_BYTES)
total_length = int.from_bytes(rawbytes[current_index:current_index + LENGTH_BYTES], 'little')
new_index = current_index + LENGTH_BYTES + total_length
assert(len(rawbytes) >= new_index)
item_index = current_index + LENGTH_BYTES

values = {}
for field_name in get_field_names(typ):
    field_name_type = get_type_for_field_name(typ, field_name)
    values[field_name], item_index = deserialize(data, item_index, field_name_type)
assert item_index == new_index
return typ(**values), item_index
```

### Tree Hash

The below `hash_tree_root_internal` algorithm is defined recursively in the case of lists and containers, and it outputs a value equal to or less than 32 bytes in size. For use as a "final output" (eg. for signing), use `hash_tree_root(x) = zpad(hash_tree_root_internal(x), 32)`, where `zpad` is a helper that extends the given `bytes` value to the desired `length` by adding zero bytes on the right:

```python
def zpad(input: bytes, length: int) -> bytes:
   return input + b'\x00' * (length - len(input))
```

Refer to [the helper function `hash`](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#hash) of Phase 0 of the [Eth2.0 specs](https://github.com/ethereum/eth2.0-specs) for a definition of the hash function used below, `hash(x)`.

#### `uint8`..`uint256`, `bool`, `bytes1`..`bytes32`

Return the serialization of the value.

#### `uint264`..`uintN`, `bytes33`..`bytesN`

Return the hash of the serialization of the value.

#### List/Vectors

First, we define the Merkle tree function.

```python
# Merkle tree hash of a list of homogenous, non-empty items
def merkle_hash(lst):
    # Store length of list (to compensate for non-bijectiveness of padding)
    datalen = len(lst).to_bytes(32, 'little')

    if len(lst) == 0:
        # Handle empty list case
        chunkz = [b'\x00' * SSZ_CHUNK_SIZE]
    elif len(lst[0]) < SSZ_CHUNK_SIZE:
        # See how many items fit in a chunk
        items_per_chunk = SSZ_CHUNK_SIZE // len(lst[0])

        # Build a list of chunks based on the number of items in the chunk
        chunkz = [
            zpad(b''.join(lst[i:i + items_per_chunk]), SSZ_CHUNK_SIZE) 
            for i in range(0, len(lst), items_per_chunk)
        ]
    else:
        # Leave large items alone
        chunkz = lst

    # Merkleise
    def next_power_of_2(x):  
        return 1 if x == 0 else 2**(x - 1).bit_length()

    for i in range(len(chunkz), next_power_of_2(len(chunkz))):
        chunkz.append(b'\x00' * SSZ_CHUNK_SIZE)
    while len(chunkz) > 1:     
        chunkz = [hash(chunkz[i] + chunkz[i+1]) for i in range(0, len(chunkz), 2)]

    # Return hash of root and data length
    return hash(chunkz[0] + datalen)
```

To `hash_tree_root_internal` a list, we simply do:

```python
return merkle_hash([hash_tree_root_internal(item) for item in value])
```

Where the inner `hash_tree_root_internal` is a recursive application of the tree-hashing function (returning less than 32 bytes for short single values).

#### Container

Recursively tree hash the values in the container in the same order as the fields, and Merkle hash the results.

```python
return merkle_hash([hash_tree_root(getattr(x, field)) for field in value.fields])
```

### Signed roots

Let `field_name` be a field name in an SSZ container `container`. We define `truncate(container, field_name)` to be the `container` with the fields from `field_name` onwards truncated away. That is, `truncate(container, field_name) = [getattr(container, field)) for field in value.fields[:i]]` where `i = value.fields.index(field_name)`.

When `field_name` maps to a signature (e.g. a BLS12-381 signature of type `Bytes96`) the convention is that the corresponding signed message be `signed_root(container, field_name) = hash_tree_root(truncate(container, field_name))`. For example if `container = {"foo": sub_object_1, "bar": sub_object_2, "signature": bytes96, "baz": sub_object_3}` then `signed_root(container, "signature") = merkle_hash([hash_tree_root(sub_object_1), hash_tree_root(sub_object_2)])`.

Note that this convention means that fields after the signature are _not_ signed over. If there are multiple signatures in `container` then those are expected to be signing over the fields in the order specified. If multiple signatures of the same value are expected the convention is that the signature field be an array of signatures.

## Implementations

| Language | Implementation                                                                                                                                                     | Description                                              |
|:--------:|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
|  Python  | [ https://github.com/ethereum/py-ssz ](https://github.com/ethereum/py-ssz) | Python implementation of SSZ |
|   Rust   | [ https://github.com/sigp/lighthouse/tree/master/beacon_chain/utils/ssz ](https://github.com/sigp/lighthouse/tree/master/beacon_chain/utils/ssz)                                                         | Lighthouse (Rust Ethereum 2.0 Node) maintained SSZ.      |
|    Nim   | [ https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim ](https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim) | Nim Implementation maintained SSZ.                       |
|   Rust   | [ https://github.com/paritytech/shasper/tree/master/util/ssz ](https://github.com/paritytech/shasper/tree/master/util/ssz)                                         | Shasper implementation of SSZ maintained by ParityTech.  |
|   Javascript   | [ https://github.com/ChainSafeSystems/ssz-js/blob/master/src/index.js ](https://github.com/ChainSafeSystems/ssz-js/blob/master/src/index.js)                                         | Javascript Implementation maintained SSZ |
|   Java   | [ https://www.github.com/ConsenSys/cava/tree/master/ssz ](https://www.github.com/ConsenSys/cava/tree/master/ssz) | SSZ Java library part of the Cava suite |
|   Go   | [ https://github.com/prysmaticlabs/prysm/tree/master/shared/ssz ](https://github.com/prysmaticlabs/prysm/tree/master/shared/ssz) | Go implementation of SSZ mantained by Prysmatic Labs |
|  Swift | [ https://github.com/yeeth/SimpleSerialize.swift ](https://github.com/yeeth/SimpleSerialize.swift) | Swift implementation maintained SSZ |
|  C# | [ https://github.com/codingupastorm/csharp-ssz ](https://github.com/codingupastorm/csharp-ssz) | C# implementation maintained SSZ |
|  C++ | [ https://github.com/NAKsir-melody/cpp_ssz](https://github.com/NAKsir-melody/cpp_ssz) | C++ implementation maintained SSZ |

## Copyright
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
