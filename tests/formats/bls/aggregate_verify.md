# Test format: BLS sign message

Verify the signature against the given pubkeys and one messages.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  pubkeys: List[bytes48] -- the pubkeys
  messages: List[bytes32] -- the messages
  signature: bytes96 -- the signature to verify against pubkeys and messages
output: bool  -- VALID or INVALID
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.
