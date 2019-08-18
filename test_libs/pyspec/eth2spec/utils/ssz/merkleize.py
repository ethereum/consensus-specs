from eth2spec.utils.hash_function import hash
from .ssz_zero_hashes import zerohashes


def merkleize_chunks(chunks, limit=None):
    # If no limit is defined, we are just merkleizing chunks (e.g. SSZ container).
    if limit is None:
        limit = len(chunks)

    count = len(chunks)
    # See if the input is within expected size.
    # If not, a list-limit is set incorrectly, or a value is unexpectedly large.
    assert count <= limit

    if limit == 0:
        return zerohashes[0]

    depth = max(count - 1, 0).bit_length()
    max_depth = (limit - 1).bit_length()
    tmp = [None for _ in range(max_depth + 1)]

    def merge(h, i):
        j = 0
        while True:
            if i & (1 << j) == 0:
                if i == count and j < depth:
                    h = hash(h + zerohashes[j])  # keep going if we are complementing the void to the next power of 2
                else:
                    break
            else:
                h = hash(tmp[j] + h)
            j += 1
        tmp[j] = h

    # merge in leaf by leaf.
    for i in range(count):
        merge(chunks[i], i)

    # complement with 0 if empty, or if not the right power of 2
    if 1 << depth != count:
        merge(zerohashes[0], count)

    # the next power of two may be smaller than the ultimate virtual size, complement with zero-hashes at each depth.
    for j in range(depth, max_depth):
        tmp[j + 1] = hash(tmp[j] + zerohashes[j])

    return tmp[max_depth]
