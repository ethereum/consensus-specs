# Test format: BLS sign message

Verify the signature against the given pubkeys and one messages.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  pubkeys: List[BLS Pubkey] -- the pubkeys
  messages: List[bytes32] -- the messages
  signature: BLS Signature -- the signature to verify against pubkeys and messages
output: bool  --  true (VALID) or false (INVALID)
```

- `BLS Pubkey` here is encoded as a string: hexadecimal encoding of 48 bytes (96
  nibbles), prefixed with `0x`.
- `BLS Signature` here is encoded as a string: hexadecimal encoding of 96 bytes
  (192 nibbles), prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `aggregate_verify` handler should verify the signature with pubkeys and
messages in the `input`, and the result should match the expected `output`.
