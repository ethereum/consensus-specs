from hashlib import sha256


def hash(x): return sha256(x).digest()
