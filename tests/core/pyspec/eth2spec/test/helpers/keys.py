from py_ecc.bls import G2ProofOfPossession as bls
from eth2spec.phase0 import spec

privkeys = [i + 1 for i in range(spec.SLOTS_PER_EPOCH * 256)]
pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}
