# BLS tests

A test type for BLS. Primarily geared towards verifying the *integration* of any BLS library.
We do not recommend rolling your own crypto or using an untested BLS library.

The BLS test suite runner has the following handlers:

- [`aggregate_pubkeys`](./aggregate_pubkeys.md)
- [`aggregate_sigs`](./aggregate_sigs.md)
- [`msg_hash_g2_compressed`](./msg_hash_g2_compressed.md)
- [`msg_hash_g2_uncompressed`](./msg_hash_g2_uncompressed.md)
- [`priv_to_pub`](./priv_to_pub.md)
- [`sign_msg`](./sign_msg.md)

*Note*: Signature-verification and aggregate-verify test cases are not yet supported.
