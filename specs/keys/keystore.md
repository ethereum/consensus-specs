# Keystores

A keystore is a JSON file which store an encrypted version of a user's private key. It is designed to be an easy-to-implement format for storing and exchanging keys. Furthermore, this specification is designed to utilize as few crypto-constructions and make a minimal number of security assumptions

![Keystore Diagram](./keystore.png)

## Definition

Private key is obtained by taking the bitwise XOR of the `ciphertext` and the `derived_key`. The `derived_key` is obtained by running scrypt with the user-provided password and the `kdfparams` obtained from within the keystore file as parameters. If a keystore file is being generated for the first time, the `salt` KDF parameter must be obtained from a CSPRNG. The `ciphertext` is simply read from the keystore file. The length of the `ciphertext` and the output key length of scrypt.

```python
def decrypt_keystore(password, dklen, n, p, r, salt, ciphertext) -> bytes
    assert len(ciphertext) == dklen
    derived_key = scrypt(password, dklen, n, p, r, salt)
    return bytes(a ^ b for a, b in zip(derived_key, ciphertext))
```

## UUIDs

The ID provided in the keystore is randomly generated and is designed to be used as a 128-bit proxy for referring to a set of keys or account. This level of abstraction provides a means of preserving privacy for a secret-key.

## Test vectors

The following test vector is taken directly from the Eth1 keystore definition:

Test values:

* Password: `testpassword`
* Secret: `7a28b5ba57c53603b0b07b56bba752f7784bf506fa95edc395f5cf6c7514fe9d` (Note that this secret is not a valid BLS12-381 private key as it is bigger than the curve order.)

```json
{
    "crypto" : {
        "ciphertext" : "d172bf743a674da9cdad04534d56926ef8358534d458fffccd4e6ad2fbde479c",
        "kdf" : "scrypt",
        "kdfparams" : {
            "dklen" : 32,
            "n" : 262144,
            "p" : 8,
            "r" : 1,
            "salt" : "ab0c7876052600dd703518d6fc3fe8984592145b591fc8fb5c6d43190334ba19"
        },
        "mac" : "2103ac29920d71da29f15d75b4a16dbe95cfd7ff8faea1056c33131d846e3097"
    },
    "id" : "3198bc9c-6672-5ab3-d995-4942343ae5b6",
    "version" : 4
}
```

## FAQs

**Why are keystores needed at all?**

Keystores provide a common interface for all clients to ingest validator credentials. By standardising this, switching between clients becomes easier as there is a common interface through which to switch.

**Why not reuse Eth1 keystores?**

* The keystores in Eth1 are more complicated than is needed and they rely on many different assumptions
* There are too many parameters and options in Eth1 keystores
* Eth1 keystores use Keccak256 which makes them unfriendly to other projects who wish to only rely on SHA256

**Why use scrypt over PBKPRF2?**\

scyrpt and PBKPRF2 both rely on the security of their underlying hash-function for their safety (SHA256), however scrypt additionally provides memory hardness. The benefit of this is greater ASIC resistance meaning brute-force attacks against scyrpt are generally slower and harder.

**Why are private keys encoded with Big Endian?**

This is done because it is how keys are stored in Eth1 and because it is is the standard of most of the crypto libraries.
