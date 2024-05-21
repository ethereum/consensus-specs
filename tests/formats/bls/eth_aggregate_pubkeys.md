<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Test format: Ethereum-customized BLS pubkey aggregation](#test-format-ethereum-customized-bls-pubkey-aggregation)
  - [Test case format](#test-case-format)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Test format: Ethereum-customized BLS pubkey aggregation

A BLS pubkey aggregation combines a series of pubkeys into a single pubkey.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input: List[BLS Pubkey] -- list of input BLS pubkeys
output: BLSPubkey -- expected output, single BLS pubkeys or `null`.
```

- `BLS Pubkey` here is encoded as a string: hexadecimal encoding of 48 bytes (96 nibbles), prefixed with `0x`.
- output value is `null` if the input is invalid.

## Condition

The `eth_aggregate_pubkeys` handler should aggregate the signatures in the `input`, and the result should match the expected `output`.
