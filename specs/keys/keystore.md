# Keystores

A keystore is a JSON file which stores a password encrypted version of a user's private key. It is designed to be an easy-to-implement, yet versatile, format for storing and exchanging keys. A keystore format that is customizable with many Key Derivation Functions (KDFs) and encryption ciphers is more future proof and thus is the model adopted by Eth1 V3 keystores. Unfortunately each option also requires implementations of the various crypto constructions and appropriate tests and therefore, this keystore standard locks down which KDF and ciphers are used for the initial phases of Eth2.0.

![Keystore Diagram](./keystore.png)

## Definition

The process of decrypting the secret held within a keystore can be broken down into 3 sub-processes: obtaining the decryption key, verifying the password and decrypting the secret. Each process has its own functions which can be selected from as well as parameters required for the function all of which are specified within the keystore file itself.

### Decryption key

The decryption key is an intermediate key which is used both to verify the user-supplied password is correct as well as for the final secret decryption. This key is simply derived from the password and the `kdfparams` using the specified `kdf` as per the keystore file.

| Function       | `"kdf"`    | `"kdfparams"` |
|----------------|------------|---------------|
| PBKDF2-SHA-256 | `"pbkdf2"` | <ul><li>`"c"`</li><li>`"dklen"`</li><li>`"prf: "hmac-sha256"`</li><li>`"salt"`</li></ul> |
| scrypt         | `"scrypt"` | <ul><li>`"dklen"`</li><li>`"n"`</li><li>`"p"`</li><li>`"r"`</li><li>`"salt"`</li></ul>|

### Password verification

The password verification verifies step verifies that the password is correct with respect to the `mac`, `ciphertext`, and `kdf`. This is done by appending the `ciphertext` to the 2nd 16 bytes of the decryption key, passing it through the `macfunction` and verifying whether it matches the `mac`.

```python
def verify_password(decryption_key: bytes, ciphertext: bytes, mac: bytes, mac_function: str,) -> bool:
    if mac_function == 'sha256':
        return sha256(decryption_key[16:31] + ciphertext) == mac
    elif mac_function == 'keccak256':
        return keccak256(decryption_key[16:31] + ciphertext) == mac
    return False
```

| Function   | `"macfunction"` |
|------------|-----------------|
| SHA-256    | `"sha256"`      |
| Keccak-256 | `"keccak256"`   |

### Secret decryption

The `cipher` encrypts the secret using the decryption key, thus to decrypt it, the decryption key along with the `cipher` and `cipherparams` must be used.

| Cipher          | `"cipher"`      | Cipher Definition                                                                       |
|-----------------|-----------------|-----------------------------------------------------------------------------------------|
| xor             | `"xor"`         | `lambda derived_key, ciphertext: bytes(a ^ b for a, b in zip(derived_key, ciphertext))` |
| AES 128 Counter | `"aes-128-ctr"` | [RFC 3686](https://tools.ietf.org/html/rfc3686)                                         |

## Keystores within Eth2.0

Initially, Eth2.0 only uses a subset of the options presented in this keystore specification to allow implementers to focus their time on other tasks which are more important in the short term. The particular `cipher`, `macfunction`, and `kdf` are specified below



Private key is obtained by taking the bitwise XOR of the `ciphertext` and the `derived_key`. The `derived_key` is obtained by running scrypt with the user-provided password and the `scryptparams` obtained from within the keystore file as parameters. If a keystore file is being generated for the first time, the `salt` KDF parameter must be obtained from a CSPRNG. The `ciphertext` is simply read from the keystore file. The length of the `ciphertext` and the output key length of scrypt.

```python
def decrypt_keystore(password: str, dklen: int, n: int, p: int, r: int, salt: bytes, ciphertext) -> bytes:
    assert len(ciphertext) == dklen
    derived_key = scrypt(password, dklen, n, p, r, salt)
    return bytes(a ^ b for a, b in zip(derived_key, ciphertext))
```

## MAC

The `mac` acts as a method for verifying that password provided by the user is indeed correct. This is done by means of an equality check between the SHA256 hash of the `derived_key` and the `mac`.

```python
def verify_password(password: str, dklen: int, n: int, p: int, r: int, salt: bytes, mac: bytes) -> bool:
    derived_key = scrypt(password, dklen, n, p, r, salt)
    return sha256(derived_key) == mac
```

## UUIDs

The `id` provided in the keystore is a randomly generated UUID and is intended to be used as a 128-bit proxy for referring to a particular set of keys or account. This level of abstraction provides a means of preserving privacy for a secret-key or for referring to keys when they are not decrypted.

## JSON schema

The keystore, at its core, is constructed with modules which allow for the configuration of the cryptographic constructions used password hashing, password verification and secret decryption. Each module is composed of: `function`, `params`, and `message` which corresponds with which construction is to be used, what the configuration for the construction is, and what the input is.

```json
{
    "$ref": "#/definitions/Keystore",
    "definitions": {
        "Keystore": {
            "type": "object",
            "properties": {
                "crypto": {
                    "type": "object",
                    "properties": {
                        "kdf": {
                            "$ref": "#/definitions/Module"
                        },
                        "checksum": {
                            "$ref": "#/definitions/Module"
                        },
                        "cipher": {
                            "$ref": "#/definitions/Module"
                        }
                    }
                },
                "id": {
                    "type": "string",
                    "format": "uuid"
                },
                "version": {
                    "type": "integer"
                }
            },
            "required": [
                "crypto",
                "id",
                "version"
            ],
            "title": "Keystore"
        },
        "Module": {
            "type": "object",
            "properties": {
                "function": {
                    "type": "string"
                },
                "params": {
                    "type": "object"
                },
                "message": {
                    "type": "string"
                }
            },
            "required": [
                "function",
                "message",
                "params"
            ]
        }
    }
}
```

## Test vectors

Test values:

* Password: `testpassword`
* Secret: `1b4b68192611faea208fca21627be9dae6c3f2564d42588fb1119dae7c9f4b87`

```json
{
    "crypto": {
        "kdf": {
            "function": "scrypt",
            "params": {
                "dklen": 32,
                "n": 262144,
                "p": 8,
                "r": 1,
                "salt": "ab0c7876052600dd703518d6fc3fe8984592145b591fc8fb5c6d43190334ba19"
            },
            "message": ""
        },
        "checksum": {
            "function": "sha256",
            "params": {},
            "message": "e1c5e3d08f8aec999df5287dd9f2b0aafdaa86d263ca6287e2bd1c6b20c19c0f"
        },
        "cipher": {
            "function": "xor",
            "params": {},
            "message": "e18afad793ec8dc3263169c07add77515d9f301464a05508d7ecb42ced24ed3a"
        }
    },
    "id": "e5e79c63-b6bc-49f2-a4f8-f0dcea550ff6",
    "version": 4
}
```

## FAQs

**Why are keystores needed at all?**

Keystores provide a common interface for all clients to ingest validator credentials. By standardizing this, switching between clients becomes easier as there is a common interface through which to switch.

**Why not reuse Eth1 keystores?**

* The keystores in Eth1 are more complicated than is needed and they rely on many different assumptions
* There are too many parameters and options in Eth1 keystores
* Eth1 keystores use Keccak256 which makes them unfriendly to other projects who wish to only rely on SHA256

**Why use scrypt over PBKDF2?**

scrypt and PBKDF2 both rely on the security of their underlying hash-function for their safety (SHA256), however scrypt additionally provides memory hardness. The benefit of this is greater ASIC resistance meaning brute-force attacks against scrypt are generally slower and harder.

**Why are private keys encoded with Big Endian?**

This is done because it is how keys are stored in Eth1 and because it is is the standard of most of the crypto libraries.
