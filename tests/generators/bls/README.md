# BLS Test Generator

Explanation of BLS12-381 type hierarchy
The base unit is bytes48 of which only 381 bits are used

- FQ: uint381 modulo field modulus
- FQ2: (FQ, FQ)
- G2: (FQ2, FQ2, FQ2)

## Resources

- [Eth2 spec](../../../specs/phase0/beacon-chain.md#bls-signatures)
- [Finite Field Arithmetic](http://www.springeronline.com/sgw/cda/pageitems/document/cda_downloaddocument/0,11996,0-0-45-110359-0,00.pdf)
- Chapter 2 of [Elliptic Curve Cryptography](http://cacr.uwaterloo.ca/ecc/). Darrel Hankerson, Alfred Menezes, and Scott Vanstone 
- [Zcash BLS parameters](https://github.com/zkcrypto/pairing/tree/master/src/bls12_381)
- [Trinity implementation](https://github.com/ethereum/trinity/blob/master/eth2/_utils/bls.py)

## Comments

Compared to Zcash, Ethereum specs always requires the compressed form (c_flag / most significant bit always set).
Also note that pubkeys and privkeys are reversed.
