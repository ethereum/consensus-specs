# BLS signature verification

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Introduction](#introduction)
- [Ciphersuite](#ciphersuite)
- [IETF function interfaces](#ietf-function-interfaces)
    - [`VALID` and `INVALID`](#valid-and-invalid)
    - [`Sign`](#sign)
    - [`Verify`](#verify)
    - [`FastAggregateVerify`](#fastaggregateverify)
- [Eth2 BLS functions](#eth2-bls-functions)
    - [`bls_sign`](#bls-sign)
    - [`bls_verify`](#bls-verify)
    - [`bls_verify_multiple`](#bls-verify-multiple)

<!-- /TOC -->

## Introduction

Eth2 makes use of the IETF BLS standards which are comprised of two documents, [BLS Signatures](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00) and [Hash to curve](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05). More precisely, [`draft-irtf-cfrg-bls-signature-00`](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00) specifies *ciphersuites* each of which define the function interfaces, parameters, serialization and test vectors for a specific BLS signature implementation. [`draft-irtf-cfrg-bls-signature-00`](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00) depends on several functions to map into the underlying curves which are specified in [`draft-irtf-cfrg-hash-to-curve-05`](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05). **Note:** although [`draft-irtf-cfrg-bls-signature-00`](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00) specifies using `hash-to-curve-04`, Eth2 makes use of `hash-to-curve-05` as it superseded v4.

## Ciphersuite

Eth2 makes use of the ciphersuite with ID `BLS_SIG_BLS12381G2-SHA256-SSWU-RO-_POP_`. As per [Section 4.2.1 of the BLS signature specification](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00#section-4.2.1), this means that `hash_to_point` suite `BLS12381G2-SHA256-SSWU-RO-` per [Section 8.9.2 of Hash to curve v5](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2) is used with domain separation tag `BLS_SIG_BLS12381G2-SHA256-SSWU-RO-_POP_`.

## IETF function interfaces

Eth2 treats all the functions defined by [`draft-irtf-cfrg-bls-signature-00`](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00) as black boxes with the following function interfaces:

### `VALID` and `INVALID`

The values `VALID` and `INVALID` used by the  IETF BLS specification are mapped to `True` and `False` respectively. This is done for notational convenience here, but may not be the case for all BLS implementations.

### `Sign`

```python
Sign(SK: int, message: Bytes) -> BLSSignature
```

### `Verify`

```python
Verify(PK: BLSPubkey, message: Bytes, signature: BLSSignature) -> bool
```

### `FastAggregateVerify`

Eth2 only aggregates signatures with the same `message` and therefore, `FastAggregateVerify` can be used.

```python
FastAggregateVerify(PK_1, ..., PK_n, message, signature) -> bool
```

## Eth2 BLS functions

This section specifies the functions that are exposed to, and used by the rest of the eth2 specifications. They act as wrapper functions over the IETF BLS functions and handle the specificities of mixing in message `tags` and argument formatting.

### `bls_sign`

```python
def bls_sign(privkey: int, message_hash: Hash, tag: Tag) -> BLSSignature:
    return Sign(privkey, message_hash + tag)
```

### `bls_verify`

```python
def bls_verify(pubkey: BLSPubkey, message_hash: Hash, signature: BLSSignature, tag: Tag) -> bool:
    return Verify(pubkey, message_hash + tag, signature)
```

### `bls_verify_multiple`

```python
def bls_verify_multiple(pubkeys: List[BLSPubkey],  message_hash: Hash, signature: BLSSignature, tag: Tag) -> bool:
    return FastAggregateVerify(*pubkeys, message_hash + tag, signature)
```
