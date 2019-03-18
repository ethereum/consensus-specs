from hashlib import sha256
from eth_utils import keccak


# def hash(x): return sha256(x).digest()
def hash(x): return keccak(x)
