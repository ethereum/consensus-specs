from py_ecc import bls

privkeys = [i + 1 for i in range(1024)]
pubkeys = [bls.privtopub(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}
