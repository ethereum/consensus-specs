# Monkey patch validator shuffling cache
_get_shuffling = get_shuffling
shuffling_cache = {}
def get_shuffling(seed: Bytes32,
                  validators: List[Validator],
                  epoch: Epoch) -> List[List[ValidatorIndex]]:

    param_hash = (seed, hash_tree_root(validators, [Validator]), epoch)

    if param_hash in shuffling_cache:
        # print("Cache hit, epoch={0}".format(epoch))
        return shuffling_cache[param_hash]
    else:
        # print("Cache miss, epoch={0}".format(epoch))
        ret = _get_shuffling(seed, validators, epoch)
        shuffling_cache[param_hash] = ret
        return ret


# Monkey patch hash cache
_hash = hash
hash_cache = {}
def hash(x):
    if x in hash_cache:
        return hash_cache[x]
    else:
        ret = _hash(x)
        hash_cache[x] = ret
        return ret
