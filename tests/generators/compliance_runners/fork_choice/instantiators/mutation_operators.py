import random


def mut_shift_(tv, idx, delta):
    time, event = tv[idx]
    new_time = int(time) + delta
    if new_time >= 0:
        return sorted(tv[:idx] + [(new_time, event)] + tv[idx + 1 :], key=lambda x: x[0])
    else:
        return idx


def mut_shift(tv, rnd: random.Random):
    idx = rnd.choice(range(len(tv)))
    idx_time = tv[idx][0]
    dir = rnd.randint(0, 1)
    if idx_time == 0 or dir:
        time_shift = rnd.randint(0, 6) * 3
    else:
        time_shift = -rnd.randint(0, idx_time // 3)
    return mut_shift_(tv, idx, time_shift)


def mut_late_arrival_(tv, idx, new_time):
    _, event = tv[idx]
    return sorted(tv[:idx] + tv[idx + 1 :] + [(new_time, event)], key=lambda x: x[0])


def mut_multi_route_(tv, idx, shifts):
    base_time, event = tv[idx]
    duplicates = [(base_time + delta, event) for delta in shifts if base_time + delta >= 0]
    return sorted(tv + duplicates, key=lambda x: x[0])


class MutationOps:
    """
    Random mutations for fork-choice event vectors.

    The active mutation set is:
    - ``shift``: move one event earlier or later in time
    - ``late_arrival``: remove an event from its original position and reinsert it
      near the tail of the test vector
    - ``multi_route``: keep the original event and add one or more shifted copies,
      modeling delivery through multiple routes
    """

    def __init__(self, start_time, seconds_per_slot, shift_bounds=(-2, 4)):
        self.start_time = int(start_time)
        self.seconds_per_slot = int(seconds_per_slot)
        self.shift_bounds = shift_bounds

    def apply_shift(self, tv, idx, delta):
        return mut_shift_(tv, idx, delta)

    def apply_late_arrival(self, tv, idx, new_time):
        return mut_late_arrival_(tv, idx, new_time)

    def apply_multi_route(self, tv, idx, deltas):
        return mut_multi_route_(tv, idx, deltas)

    def apply_mutation(self, tv, op_kind, *params):
        if op_kind == "shift":
            return self.apply_shift(tv, *params)
        elif op_kind == "late_arrival":
            return self.apply_late_arrival(tv, *params)
        elif op_kind == "multi_route":
            return self.apply_multi_route(tv, *params)
        else:
            assert False

    def rand_shift(self, time: int, rnd: random.Random) -> int:
        assert time >= self.start_time
        neg_shift, pos_shift = self.shift_bounds
        min_shift = max(self.start_time - time, neg_shift * self.seconds_per_slot)
        max_shift = pos_shift * self.seconds_per_slot
        if rnd.randint(0, 1) == 0:
            return rnd.randint(min_shift, 0)
        else:
            return rnd.randint(1, max_shift)

    def rand_late_arrival_time(self, tv, rnd: random.Random) -> int:
        last_time = max(int(time) for time, _ in tv)
        extra_slots = rnd.randint(1, 3)
        return last_time + extra_slots * self.seconds_per_slot

    def rand_multi_route_shifts(self, time: int, rnd: random.Random) -> tuple[int, ...]:
        shifts = [self.rand_shift(time, rnd)]
        if rnd.randint(0, 1) == 1:
            last_time = abs(self.shift_bounds[1]) * self.seconds_per_slot
            shifts.append(rnd.randint(1, max(1, last_time)))
        return tuple(shifts)

    def rand_mutation(self, tv, rnd: random.Random):
        idx = rnd.choice(range(len(tv)))
        op_kind = rnd.choice(["shift", "late_arrival", "multi_route"])
        if op_kind == "shift":
            evt_time = int(tv[idx][0])
            params = idx, self.rand_shift(evt_time, rnd)
        elif op_kind == "late_arrival":
            params = idx, self.rand_late_arrival_time(tv, rnd)
        elif op_kind == "multi_route":
            evt_time = int(tv[idx][0])
            params = idx, self.rand_multi_route_shifts(evt_time, rnd)
        else:
            assert False
        return op_kind, *params

    def rand_mutations(self, tv, num, rnd: random.Random):
        mutations = []
        for _ in range(num):
            if len(tv) == 0:
                break
            mut_op = self.rand_mutation(tv, rnd)
            mutations.append(mut_op)
            tv = self.apply_mutation(tv, *mut_op)
        return tv, mutations
