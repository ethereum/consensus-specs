from py_ecc.bls import G2ProofOfPossession as bls

# Enough keys for 256 validators per slot in worst-case epoch length
privkeys = [i + 1 for i in range(32 * 256)]
pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}
