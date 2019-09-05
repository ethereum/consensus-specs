# Keystores

A keystore is a JSON file which stores a password encrypted version of a user's private key. It is designed to be an easy-to-implement, yet versatile, format for storing and exchanging keys. A keystore format that is customizable with many Key Derivation Functions (KDFs) and encryption ciphers is more future proof and thus is the model adopted by Eth1 V3 keystores. Unfortunately each option also requires implementations of the various crypto constructions and appropriate tests and therefore, this keystore standard locks down which KDF and ciphers are used for the initial phases of Eth2.0.

![Keystore Diagram](./keystore.png)

## Definition

The process of decrypting the secret held within a keystore can be broken down into 3 sub-processes: obtaining the decryption key, verifying the password and decrypting the secret. Each process has its own functions which can be selected from as well as parameters required for the function all of which are specified within the keystore file itself.

### Decryption key

The decryption key is an intermediate key which is used both to verify the user-supplied password is correct as well as for the final secret decryption. This key is simply derived from the password, the `function`, and the `params` specified by the`kdf` module as per the keystore file.

| KDF            | `"function"` | `"params"` | `"message"` |
|----------------|--------------|------------|-------------|
| PBKDF2-SHA-256 | `"pbkdf2"`   | <ul><li>`"c"`</li><li>`"dklen"`</li><li>`"prf: "hmac-sha256"`</li><li>`"salt"`</li></ul> |  |
| scrypt         | `"scrypt"`   | <ul><li>`"dklen"`</li><li>`"n"`</li><li>`"p"`</li><li>`"r"`</li><li>`"salt"`</li></ul>|  |

### Password verification

The password verification verifies step verifies that the password is correct with respect to the `checksum.message`, `cipher.message`, and `kdf`. This is done by appending the `cipher.message` to the 2nd 16 bytes of the decryption key, passing it through the function specified by`checksum.function` and verifying whether it matches the `checksum.message`.

```python
def is_valid_password(decryption_key: bytes, cipher_message: bytes, checksum_message: bytes, checksum_function: str,) -> bool:
    if checksum_function == 'sha256':
        return sha256(decryption_key[16:31] + checksum_message) == mac
    elif checksum_function == 'keccak256':
        return keccak256(decryption_key[16:31] + checksum_message) == mac
    return False
```

| Hash       | `"function"`    | `"params"` | `"message"` |
|------------|-----------------|------------|-------------|
| SHA-256    | `"sha256"`      |  |
| Keccak-256 | `"keccak256"`   |  |

### Secret decryption

The `cipher.function` encrypts the secret using the decryption key, thus to decrypt it, the decryption key along with the `cipher.function` and `cipher.params` must be used.

| Cipher          | `"function"`    | `"params"` | `"message"` | Cipher Definition                                                                       |
|-----------------|-----------------|------------|-------------|-----------------------------------------------------------------------------------------|
| XOR             | `"xor"`         |            |             | `lambda decryption_key, cipher_message: bytes(a ^ b for a, b in zip(decryption_key, cipher_message))` |
| AES 128 Counter | `"aes-128-ctr"` |            |             | [RFC 3686](https://tools.ietf.org/html/rfc3686)                                         |

## UUIDs

The `id` provided in the keystore is a randomly generated UUID and is intended to be used as a 128-bit proxy for referring to a particular set of keys or account. This level of abstraction provides a means of preserving privacy for a secret-key or for referring to keys when they are not decrypted.

## Keystores within Eth2.0

Initially, Eth2.0 only uses a subset of the options presented in this keystore specification to allow implementers to focus their time on other tasks that are more important in the short term. The particular `cipher`, `checksum`, and `kdf` functions are specified below:

* **KDF:** scrypt
* **Checksum:** SHA256
* **Cipher:** XOR

### Python implementation

```python
def get_decryption_key(password: str, kdf_params_dklen: int,
                       kdf_params_n: int, kdf_params_p: int, kdf_params_salt: bytes) -> bytes:
    return scrypt(password, kdf_params_dklen, kdf_params_n, kdf_params_p, kdf_params_r, kdf_params_salt)
```

```python
def verify_password(decryption_key: bytes, cipher_message: bytes, checksum_message: bytes):
    assert sha256(decryption_key[16:31] + cipher_message) == checksum_message
```

```python
def get_private_key(decryption_key: bytes, cipher_message: bytes):
    assert len(decryption_key) == len(cipher_message)
    return bytes(a ^ b for a, b in zip(decryption_key, cipher_message))
```

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

The following test is a valid test for the initial Eth2.0 keystore definition.

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
