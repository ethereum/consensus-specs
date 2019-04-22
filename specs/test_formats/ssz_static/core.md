# Test format: SSZ static types

The goal of this type is to provide clients with a solid reference how the known SSZ objects should be encoded.
Each object described in the Phase-0 spec is covered.
This is important, as many of the clients aiming to serialize/deserialize objects directly into structs/classes
do not support (or have alternatives for) generic SSZ encoding/decoding.
This test-format ensures these direct serializations are covered.

## Test case format

```yaml
type_name: string  -- string, object name, formatted as in spec. E.g. "BeaconBlock"
value: dynamic     -- the YAML-encoded value, of the type specified by type_name.
serialized: bytes  -- string, SSZ-serialized data, hex encoded, with prefix 0x
root: bytes32      -- string, hash-tree-root of the value, hex encoded, with prefix 0x
signing_root: bytes32 -- string, signing-root of the value, hex encoded, with prefix 0x. Optional, present if type contains ``signature`` field
```

## Condition

A test-runner can implement the following assertions:
- Serialization: After parsing the `value`, SSZ-serialize it: the output should match `serialized`
- Hash-tree-root: After parsing the `value`, Hash-tree-root it: the output should match `root`
    - Optionally also check signing-root, if present.
- Deserialization: SSZ-deserialize the `serialized` value, and see if it matches the parsed `value`

## References


**`serialized`**: [SSZ serialization](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md#serialization)   
**`root`** - [hash_tree_root](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md#merkleization)
**`signing_root`** - [signing_root](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md#self-signed-containers)
