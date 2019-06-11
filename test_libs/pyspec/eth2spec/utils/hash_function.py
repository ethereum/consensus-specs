from hashlib import sha256

ZERO_BYTES32 = b'\x00' * 32

def _hash(x):
    return sha256(x).digest()

zerohashes = [(None, ZERO_BYTES32)]
for layer in range(1, 32):
    k = zerohashes[layer - 1][1] + zerohashes[layer - 1][1]
    zerohashes.append((k, _hash(k)))
zerohashes = zerohashes[1:]


def hash(x):
    for (k, h) in zerohashes:
        if x == k:
            return h
    return _hash(x)
