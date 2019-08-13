# Keys and their storage within Ethereum 2.0

## Validator withdrawal and signing keys

### Withdrawal keys

A validator's withdrawal key is defined at the account level and does not utilize further levels. Thus a validator's withdrawal key is given by `m / 12381' / 60 ' /  x'` where `x` is used to obtain separate keys for the various validator instances needed.

### Signing keys

Signing keys are derivable from withdrawal keys, this is achieved by defining the signing key as the 0th hardened address of a validator's signing key. Thus,the path of a validator's signing key is defined by `m / 12381' / 60 ' /  x' / 0 '`
