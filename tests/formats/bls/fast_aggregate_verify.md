# Test format: BLS fast aggregate verify

Verify the signature against the given pubkeys and one message.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  pubkeys: List[BLS Pubkey] -- list of input BLS pubkeys
  message: bytes32 -- the message
  signature: BLS Signature -- the signature to verify against pubkeys and message
output: bool  --  true (VALID) or false (INVALID)
```

- `BLS Pubkey` here is encoded as a string: hexadecimal encoding of 48 bytes (96
  nibbles), prefixed with `0x`.
- `BLS Signature` here is encoded as a string: hexadecimal encoding of 96 bytes
  (192 nibbles), prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `fast_aggregate_verify` handler should verify the signature with pubkeys and
message in the `input`, and the result should match the expected `output`.
