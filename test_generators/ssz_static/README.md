# SSZ-static

The purpose of this test-generator is to provide test-vectors for the most important applications of SSZ:
 the serialization and hashing of ETH 2.0 data types

#### Test case
Example:
```yaml
- type_name: DepositData
  value: {pubkey: '0x364194dbcda9974ec8e57aa0d556ced515e43ce450e21aa8f9b2099a528679fcf45aed142db60b7f848bd399b63f0933',
    withdrawal_credentials: '0xad1256c89ae823b24e1d81fae3d3d382d60012d8399f469ff404e3bbf908027a',
    amount: 2672254660871140633, signature: '0x5c3fe3bdbf58d0fb4cdb63a19a67082c697ef910c182dc824c8fb048c935b4b46f522c36047ae36feef84654c1e868f3a0edd76852c09e35414782160767439b49aceaa4219cc25016effcc82a9e17b336efee40ab37e3a47fc31da557027491'}
  serialized: '0x364194dbcda9974ec8e57aa0d556ced515e43ce450e21aa8f9b2099a528679fcf45aed142db60b7f848bd399b63f0933ad1256c89ae823b24e1d81fae3d3d382d60012d8399f469ff404e3bbf908027a19359bb274c115255c3fe3bdbf58d0fb4cdb63a19a67082c697ef910c182dc824c8fb048c935b4b46f522c36047ae36feef84654c1e868f3a0edd76852c09e35414782160767439b49aceaa4219cc25016effcc82a9e17b336efee40ab37e3a47fc31da557027491'
  root: '0x2eaae270579fc1a1eabde69c841221cb3dfab9de7ad99fcfbee8fe0c198878b7'
  signing_root: '0x844655facb151b633410ffc698d8467c6488ae87f2d5f739d39c9bfc18750524'
```
**type_name** - Name of valid Eth2.0 type from the spec   
**value** - Field values used to create type instance  
**serialized** - [SSZ serialization](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md#serialization) of the value      
**root** - [hash_tree_root](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md#merkleization) of the value  
**signing_root** - (Optional) [signing_root](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/simple-serialize.md#self-signed-containers) of the value, if type contains ``signature`` field