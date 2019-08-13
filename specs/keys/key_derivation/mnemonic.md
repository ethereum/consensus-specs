# Mnemonics, recovery, and seed generation

This mnemonic generation strategy is largely based on that of [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) and thus uses the same algorithms and wordlists with a few exceptions in the interests of security and simplicity.

## What is different compared to BIP32

This document is the same as BIP32 save for the following exceptions:

* HMAC-SHA512 is replaced with HKDF-SHA256
* Only 256-bit entropy seeds are utilized to generate the mnemonic and therefore all mnemonics are 24 words long
* The seed derived from the mnemonic uses scrypt in lieu of PBKDF2

## Generating the mnemonic

The mnemonic is comprised of 24 words chosen from one of the wordlists separated by spaces. The first 23 words are chosen using a CSPRNG and the final word acts as a checksum.

In order to derive the mnemonic, first 256 bits are sampled from a CSPRNG (henceforth called `entropy`). Next a checksum is calculated by taking the SHA256 hash of `entropy`, the leading 8 bits of which are appended to `entropy`. The resultant 264 bits are then split into groups of 11 bits, each of which are parsed as integers (using big endian) and used to look up the index of the word from the wordlist.

These words are then joined into a single string separated by spaces.

```python
def get_mnemonic(entropy: bytes) -> str:
    entropy_length = len(entropy) * 8
    assert entropy_length == 256
    checksum_length = 8
    checksum = int.from_bytes(sha256(entropy), 'big') >> 256 - checksum_length
    entropy_bits = int.from_bytes(entropy, 'big') << checksum_length
    entropy_bits += checksum
    entropy_length += checksum_length
    mnemonic = []
    for i in range(entropy_length // 11 - 1, -1, -1):
        index = (entropy_bits >> i * 11) & 2**11 - 1
        mnemonic.append(get_word(index))
    return ' '.join(mnemonic)
```

## Deriving the seed from the mnemonic

The seed is derived from the mnemonic and is used as the building point for obtaining more keys. The seed is designed to be the source of entropy for the master node in the [tree KDF](./tree_kdf.md). The seed is derived by passing the mnemonic and the password `"mnemonic" + password` (where `password=''` if the users does not supply one) into the scrypt key derivation function (defined in [RFC 7914](https://tools.ietf.org/html/rfc7914)). The mnemonic and password are both encoded in Unicode NFKD format.

The parameters for scrypt are as follows:

* `n = 2**18`
* `r = 1`
* `p = 8`
* `key_length = 32  # bytes`

Thus, the seed derivation function is given by:

```python
def get_seed(*, mnemonic: str, password: str='') -> bytes:
    mnemonic = normalize('NFKD', mnemonic)
    password = normalize('NFKD', 'mnemonic' + password)
    return scrypt(password=mnemonic, salt=password, n=2**18, r=1, p=8, dklen=32)

```
