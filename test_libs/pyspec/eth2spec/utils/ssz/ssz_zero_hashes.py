ZERO_BYTES32 = b'\x00' * 32

zerohashes = [ZERO_BYTES32]
for layer in range(1, 100):
    zerohashes.append(hash(zerohashes[layer - 1] + zerohashes[layer - 1]))

