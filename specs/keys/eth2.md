# Keys and their storage within Ethereum 2.0

## Validator withdrawal and signing keys

A validator's withdrawal and signing keys are elements of the key-tree as described below. They are designed to be stored in [keystore files](./eth2.md) with the idea being that clients need only concern themselves with ingesting a signing-key keystore and that this sufficient for a to launch a validator instance.

### Withdrawal keys

A validator's withdrawal key is defined at the "other" level. Thus a validator's withdrawal key is given by `m / 12381' / 60 ' /  x' / 0'` where `x` is used to obtain separate keys for the various validator instances needed.

### Signing keys

Signing keys are derivable from withdrawal keys, this is achieved by defining the signing key as the 0th hardened child of a validator's withdrawal key. Thus,the path of a validator's signing key is defined by `m / 12381' / 60 ' /  x' / 0' / 0'`.
