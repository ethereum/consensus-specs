# Pubkey encoding

Pubkeys are G1 elements as specified in [`bls_signature.md`](./bls_signature.md), however they are further encoded with [Bech32](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki) to provide error detection.

## Bech32 in Eth2.0

Eth2.0's use of Bech32 is almost entirely compliant with the specification save for the lack of witnesses which appear in the original. Bech32 defines a human-readable part, a separator, and data part which are used to specify the target chain as well as the data for said chain. The general format for an Eth2.0 pubkey is as follows:

`e21qq[77-char pubkey][6-char checksum]`

Where the above characters represent:

* `e2` - Indicates that this is an **E**th**2**.0 pubkey
* `1` - Separator between the human-readable part and data
* `qq` - Decodes to `0` reserved for future versioning use
* `[77-char pubkey]` - Bech32-alphabet encoded pubkey as per the 48 bytes specified by [`bls_signature.md`](./bls_signature.md)
* `[6-char checksum]` - The checksum as defined by the Bech32 standard

## Uppercase/lowercase

Eth2.0 Bech32 encoded keys SHOULD be encoded with lowercase characters as per the Bech32 standard and mixed case MUST NOT be used.
