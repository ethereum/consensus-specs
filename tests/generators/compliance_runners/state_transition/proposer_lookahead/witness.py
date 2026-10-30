"""Construct distinct proposer witnesses without changing the candidate count."""

from functools import cache


def distinct_proposer_balances(spec, state, epoch, indices, *, max_nodes=2000):
    """Find balance thresholds making each slot select a different candidate.

    A draw accepts a validator above its random threshold. Choosing a slot's
    proposer therefore imposes a lower bound on its balance and upper bounds
    for the preceding draws. Search these finite constraints across slots,
    requiring distinct winners. Balances are multiples of the spec increment.
    """
    count = len(indices)
    slots = int(spec.SLOTS_PER_EPOCH)
    if count < slots:
        raise ValueError("distinct proposers require at least one candidate per slot")
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    maximum = int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA) // increment
    seed = spec.get_seed(state, spec.Epoch(epoch), spec.DOMAIN_BEACON_PROPOSER)
    start_slot = int(spec.compute_start_slot_at_epoch(spec.Epoch(epoch)))
    return _balances_for_seed(spec, seed, start_slot, count, slots, maximum, increment, max_nodes)


@cache
def _balances_for_seed(spec, seed, start_slot, count, slots, maximum, increment, max_nodes):
    choices = []
    for slot in range(start_slot, start_slot + slots):
        slot_seed = spec.sha256(seed + spec.uint_to_bytes(spec.Slot(slot)))
        caps = {}
        options = []
        for draw in range(count * 2):
            offset = draw % 16 * 2
            if offset == 0:
                random_bytes = spec.sha256(slot_seed + spec.uint_to_bytes(spec.Uint64(draw // 16)))
            random_value = int.from_bytes(random_bytes[offset : offset + 2], "little")
            threshold = (maximum * random_value + 65534) // 65535
            candidate = int(
                spec.compute_shuffled_index(
                    spec.Uint64(draw % count),
                    spec.Uint64(count),
                    slot_seed,
                )
            )
            if threshold <= caps.get(candidate, maximum):
                options.append((candidate, threshold, tuple(caps.items())))
            if threshold == 0:
                break  # This draw cannot be rejected, even by a zero balance.
            caps[candidate] = min(caps.get(candidate, maximum), threshold - 1)
        choices.append(options)

    nodes = 0

    def search(pending, lower, upper, used):
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            return None
        if not pending:
            return lower
        best_slot, best_options = None, None
        for slot in pending:
            options = [
                option
                for option in choices[slot]
                if not (used & (1 << option[0]))
                and option[1] <= upper[option[0]]
                and all(cap >= lower[index] for index, cap in option[2])
            ]
            if not options:
                return None
            if best_options is None or len(options) < len(best_options):
                best_slot, best_options = slot, options
        remaining = tuple(slot for slot in pending if slot != best_slot)
        for candidate, threshold, caps in best_options:
            next_lower, next_upper = lower.copy(), upper.copy()
            for index, cap in caps:
                next_upper[index] = min(next_upper[index], cap)
            next_lower[candidate] = max(next_lower[candidate], threshold)
            if next_lower[candidate] > next_upper[candidate]:
                continue
            result = search(remaining, next_lower, next_upper, used | (1 << candidate))
            if result is not None:
                return result
        return None

    result = search(tuple(range(slots)), [0] * count, [maximum] * count, 0)
    return None if result is None else [balance * increment for balance in result]
