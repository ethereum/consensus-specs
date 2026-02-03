# Altair -- BLS extensions

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Extensions](#extensions)
  - [`eth_aggregate_pubkeys`](#eth_aggregate_pubkeys)
  - [`eth_fast_aggregate_verify`](#eth_fast_aggregate_verify)

<!-- mdformat-toc end -->

## Introduction

A number of extensions are defined to handle BLS signatures in the Altair
upgrade.

Knowledge of the [phase 0 specification](../phase0/beacon-chain.md) is assumed,
including type definitions.

## Constants

| Name                   | Value                                  |
| ---------------------- | -------------------------------------- |
| `G2_POINT_AT_INFINITY` | `BLSSignature(b'\xc0' + b'\x00' * 95)` |

## Extensions

### `eth_aggregate_pubkeys`

An additional function `AggregatePKs` is defined to extend the
[IETF BLS signature draft standard v4](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-04)
specification referenced in the phase 0 document.

```python
def eth_aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    """
    Return the aggregate public key for the public keys in ``pubkeys``.

    Note: the ``+`` operation should be interpreted as elliptic curve point addition, which takes as input
    elliptic curve points that must be decoded from the input ``BLSPubkey``s.
    This implementation is for demonstrative purposes only and ignores encoding/decoding concerns.
    Refer to the BLS signature draft standard for more information.
    """
    assert len(pubkeys) > 0
    # Ensure that the given inputs are valid pubkeys
    assert all(bls.KeyValidate(pubkey) for pubkey in pubkeys)

    result = copy(pubkeys[0])
    for pubkey in pubkeys[1:]:
        result += pubkey
    return result
```

### `eth_fast_aggregate_verify`

```python
def eth_fast_aggregate_verify(
    pubkeys: Sequence[BLSPubkey], message: Bytes32, signature: BLSSignature
) -> bool:
    """
    Wrapper to ``bls.FastAggregateVerify`` accepting the ``G2_POINT_AT_INFINITY`` signature when ``pubkeys`` is empty.
    """
    if len(pubkeys) == 0 and signature == G2_POINT_AT_INFINITY:
        return True
    return bls.FastAggregateVerify(pubkeys, message, signature)
```
