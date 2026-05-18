# Test format: BLS sign message

Verify the signature against the given one pubkey and one message.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  pubkey: bytes48 -- the pubkey
  message: bytes32 -- the message
  signature: bytes96 -- the signature to verify against pubkey and message
output: bool  -- VALID or INVALID
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.
