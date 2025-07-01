# BLS tests

A test type for BLS. Primarily geared towards verifying the *integration* of any
BLS library. We do not recommend rolling your own crypto or using an untested
BLS library.

The BLS test suite runner has the following handlers:

- [`aggregate_verify`](./aggregate_verify.md)
- [`aggregate`](./aggregate.md)
- [`eth_aggregate_pubkeys`](./eth_aggregate_pubkeys.md)
- [`eth_fast_aggregate_verify`](./eth_fast_aggregate_verify.md)
- [`fast_aggregate_verify`](./fast_aggregate_verify.md)
- [`sign`](./sign.md)
- [`verify`](./verify.md)

*Note*: Signature-verification and aggregate-verify test cases are not yet
supported.
