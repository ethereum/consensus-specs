### BLS Verification

See https://z.cash/blog/new-snark-curve/ for BLS-12-381 parameters.

We represent a point in G1 as a 384-bit integer `z`, where `x = z % 2**383` and `y` is the point such that `y % 2 == z // 2**383` and (x, y) is a curve point. We represent a point in G2 as a pair of 384-bit integers `(z1, z2)` where `x = (z1 % 2**383) + z2 * i` and `y` is the point such that the real part of `y` satisfies `y_real % 2 == z1 // 2**383` and `(x, y)` is a curve point. Verifying validity of a G1 or G2 point includes verifying that it is in the correct subgroup, ie. `(x, y) * r` is the point at infinity.

`BLSVerify(pubkey: uint384, msg: bytes32, sig: [uint384])` is done as follows:

* Verify that `pubkey` is a valid G1 point and `sig` is a valid G2 point.
* Convert `msg` to a G2 point using `hash_to_G2` defined below.
* Do the pairing check: verify `e(pubkey, hash_to_G2(msg)) == e(G1, sig)`

Here is the `hash_to_G2` definition:

```python
# See https://github.com/zkcrypto/pairing/tree/master/src/bls12_381
G2_cofactor = 305502333931268344200999753193121504214466019254188142667664032982267604182971884026507427359259977847832272839041616661285803823378372096355777062779109
field_modulus = 0x1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaab

def hash_to_G2(m):
    # TODO
```



(see 
