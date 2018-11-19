### BLS Verification

See https://z.cash/blog/new-snark-curve/ for BLS-12-381 parameters.

We represent coordinates as defined in https://github.com/zkcrypto/pairing/tree/master/src/bls12_381/.

Specifically, a point in G1 as a 384-bit integer `z`, which we decompose into `x = z % 2**381`, `highflag = z // 2**382` and `lowflag = (z % 2**382) // 2**381`. If `highflag == 3`, the point is the point at infinity and we require `lowflag = x = 0`. Otherwise, we require `highflag == 2`, in which case the point is `(x, y)` where `y` is the valid coordinate such that `(y * 2) // q == lowflag`.

We represent a point in G2 as a pair of 384-bit integers `(z1, z2)` that are each decomposed into `x1`, `highflag1`, `lowflag1`, `x2`, `highflag2`, `lowflag2` as above. We require `lowflag2 = highflag2 = 0`. If `highflag1 == 3`, the point is the point at infinity and we require `lowflag1 = x1 = x2 = 0`. Otherwise, we require `highflag == 2`, in which case the point is `(x1 * i + x2, y)` where `y` is the valid coordinate such that the imaginary part of `y` satisfies `(y_im * 2) // q == lowflag1`.

`BLSVerify(pubkey: uint384, msg: bytes32, sig: [uint384], domain: uint64)` is done as follows:

* Verify that `pubkey` is a valid G1 point and `sig` is a valid G2 point.
* Convert `msg` to a G2 point using `hash_to_G2` defined below.
* Do the pairing check: verify `e(pubkey, hash_to_G2(msg)) == e(G1, sig)`

Here is the `hash_to_G2` definition:

```python
G2_cofactor = 305502333931268344200999753193121504214466019254188142667664032982267604182971884026507427359259977847832272839041616661285803823378372096355777062779109
field_modulus = 0x1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaab

def hash_to_G2(m, domain):
    # todo
    return hash_to_point(hash(bytes8(domain) + m))
```

`BLSMultiVerify(pubkeys: [uint384], msgs: [bytes32], sig: [uint384], domain: uint64)` is done as follows:

* Verify that each element of `pubkeys` is a valid G1 point and `sig` is a valid G2 point.
* Convert each element of `mssg` to a G2 point using `hash_to_G2` defined above.
* Check that the length of `pubkeys` and `msgs` is the same, call the length `L`
* Do the pairing check: verify `e(pubkeys[0], hash_to_G2(msgs[0])) * ... * e(pubkeys[L-1], hash_to_G2(msgs[L-1])) == e(G1, sig)`
