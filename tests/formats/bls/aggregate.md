<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Test format: BLS signature aggregation](#test-format-bls-signature-aggregation)
  - [Test case format](#test-case-format)
  - [Condition](#condition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Test format: BLS signature aggregation

A BLS signature aggregation combines a series of signatures into a single signature.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input: List[BLS Signature] -- list of input BLS signatures
output: BLS Signature -- expected output, single BLS signature or `null`.
```

- `BLS Signature` here is encoded as a string: hexadecimal encoding of 96 bytes (192 nibbles), prefixed with `0x`.
- output value is `null` if the input is invalid.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.

## Condition

The `aggregate` handler should aggregate the signatures in the `input`, and the result should match the expected `output`.
