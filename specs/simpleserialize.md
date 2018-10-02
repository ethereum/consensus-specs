# SimpleSerialize (SSZ) Spec

***Work In Progress***

This is the work in progress document to describe `simpleserialize`, the
current selected serialization method for Ethereum 2.0 using the Beacon Chain.

This document specifies the general information for serializing and
deserializing objects and data types.

## ToC

* [About](#about)
* [Terminology](#terminology)
* [Constants](#constants)
* [Overview](#overview)
 + [Serialize/Encode](#serializeencode)
   - [uint: 8/16/24/32/64/256](#uint-816243264256)
   - [Address](#address)
   - [Hash32](#hash32)
   - [Bytes](#bytes)
   - [List](#list)
 + [Deserialize/Decode](#deserializedecode)
   - [uint: 8/16/24/32/64/256](#uint-816243264256-1)
   - [Address](#address-1)
   - [Hash32](#hash32-1)
   - [Bytes](#bytes-1)
   - [List](#list-1)
* [Implementations](#implementations)

## About

`SimpleSerialize` was first proposed by Vitalik Buterin as the serializaiton
protocol for use in the Ethereum 2.0 Beacon Chain.

The core feature of `ssz` is the simplicity of the serialization with low
overhead.

## Terminology

| Term         | Definition                                                                                     |
|:-------------|:-----------------------------------------------------------------------------------------------|
| `big`        | Big Endian                                                                                     |
| `byte_order` | Specifies [endianness:](https://en.wikipedia.org/wiki/Endianness) Big Endian or Little Endian. |
| `len`        | Length/Number of Bytes.                                                                        |
| `to_bytes`   | Convert to bytes. Should take parameters ``size`` and ``byte_order``.                          |
| `from_bytes` | Convert form bytes to object. Should take ``bytes`` and ``byte_order``.                        |
| `value`      | The value to serialize.                                                                        |
| `rawbytes`   | Raw serialized bytes.                                                                          |

## Constants

| Constant       | Value | Definition                                                              |
|:---------------|:-----:|:------------------------------------------------------------------------|
| `LENGTH_BYTES` |   4   | Number of bytes used for the length added before the serialized object. |


## Overview

### Serialize/Encode

#### uint: 8/16/24/32/64/256

Convert directly to bytes the size of the int. (e.g. ``uint16 = 2 bytes``)

All integers are serialized as **big endian**.

| Check to perform                 | Code                    |
|:---------------------------------|:------------------------|
| Size is a byte integer           | ``int_size % 8 == 0``   |
| Value is less than max           | ``2**int_size > value`` |

```python
buffer_size = int_size / 8
return value.to_bytes(buffer_size, 'big')
```

#### Address

The address should already come as a hash/byte format. Ensure that length is
**20**.

| Check to perform       | Code                 |
|:-----------------------|:---------------------|
| Length is correct (20) | ``len(value) == 20`` |

```python
assert( len(value) == 20 )
return value
```

#### Hash32

The hash32 should already be a 32 byte length serialized data format. The safety
check ensures the 32 byte length is satisfied.

| Check to perform       | Code                 |
|:-----------------------|:---------------------|
| Length is correct (32) | ``len(value) == 32`` |

```python
assert( len(value) == 32 )
return value
```

#### Bytes

For general `byte` type:
1. Get the length/number of bytes; Encode into a 4 byte integer.
2. Append the value to the length and return: ``[ length_bytes ] + [
   value_bytes ]``

| Check to perform                     | Code                   |
|:-------------------------------------|:-----------------------|
| Length of bytes can fit into 4 bytes | ``len(value) < 2**32`` |

```python
byte_length = (len(value)).to_bytes(4, 'big')
return byte_length + value
```

#### List

For lists of values, get the length of the list and then serialize the value
of each item in the list:
1. For each item in list:
   1. serialize.
   2. append to string.
2. Get size of serialized string. Encode into a 4 byte integer.

```python
serialized_list_string = ''

for item in value:
   serialized_list_string += serialize(item)

serialized_len = len(serialized_list_string)

return serialized_len + serialized_list_string
```

### Deserialize/Decode

The decoding requires knowledge of the type of the item to be decoded. When
performing decoding on an entire serialized string, it also requires knowledge
of what order the objects have been serialized in.

Note: Each return will provide ``deserialized_object, new_index`` keeping track
of the new index.

At each step, the following checks should be made:

| Check Type               | Check                                                     |
|:-------------------------|:----------------------------------------------------------|
| Ensure sufficient length | ``length(rawbytes) > current_index + deserialize_length`` |

#### uint: 8/16/24/32/64/256

Convert directly from bytes into integer utilising the number of bytes the same
size as the integer length. (e.g. ``uint16 == 2 bytes``)

All integers are interpreted as **big endian**.

```python
byte_length = int_size / 8
new_index = current_index + int_size
return int.from_bytes(rawbytes[current_index:current_index+int_size], 'big'), new_index
```

#### Address

Return the 20 bytes.

```python
new_index = current_index + 20
return rawbytes[current_index:current_index+20], new_index
```

#### Hash32

Return the 32 bytes.

```python
new_index = current_index + 32
return rawbytes[current_index:current_index+32], new_index
```

#### Bytes

Get the length of the bytes, return the bytes.

```python
bytes_length = int.from_bytes(rawbytes[current_index:current_index+4], 'big')
new_index = current_index + 4 + bytes_lenth
return rawbytes[current_index+4:current_index+4+bytes_length], new_index
```

#### List

Deserialize each object in the list.
1. Get the length of the serialized list.
2. Loop through deserializing each item in the list until you reach the
entire length of the list.


| Check type                          | code                                  |
|:------------------------------------|:--------------------------------------|
| rawbytes has enough left for length | ``len(rawbytes) > current_index + 4`` |

```python
total_length = int.from_bytes(rawbytes[current_index:current_index+4], 'big')
new_index = current_index + 4 + total_length
item_index = current_index + 4
deserialized_list = []

while item_index < new_index:
   object, item_index = deserialize(rawbytes, item_index, item_type)
   deserialized_list.append(object)

return deserialized_list, new_index
```

## Implementations

| Language | Implementation                                                                                                                                                     | Description                                              |
|:--------:|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
|  Python  | [ https://github.com/ethereum/beacon_chain/blob/master/ssz/ssz.py ](https://github.com/ethereum/beacon_chain/blob/master/ssz/ssz.py)                               | Beacon chain reference implementation written in Python. |
|   Rust   | [ https://github.com/sigp/lighthouse/tree/master/ssz ](https://github.com/sigp/lighthouse/tree/master/ssz)                                                         | Lighthouse (Rust Ethereum 2.0 Node) maintained SSZ.      |
|    Nim   | [ https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim ](https://github.com/status-im/nim-beacon-chain/blob/master/beacon_chain/ssz.nim) | Nim Implementation maintained SSZ.                       |
|   Rust   | [ https://github.com/paritytech/shasper/tree/master/util/ssz ](https://github.com/paritytech/shasper/tree/master/util/ssz)                                         | Shasper implementation of SSZ maintained by ParityTech.  |
