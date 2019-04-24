from py_ecc import bls
from eth2spec.phase0.spec import hash

privkeys = list(range(1, 101))
pubkeys = [bls.privtopub(k) for k in privkeys]
# Insecure, but easier to follow
withdrawal_creds = [hash(bls.privtopub(k)) for k in privkeys]
