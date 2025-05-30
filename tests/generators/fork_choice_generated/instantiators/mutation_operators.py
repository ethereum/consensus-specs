import random


def mut_shift_(tv, idx, delta):
    time, event = tv[idx]
    new_time = int(time) + delta
    if new_time >= 0:
        return sorted(tv[:idx] + [(new_time, event)] + tv[idx+1:], key=lambda x: x[0])
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


def mut_drop_(tv, idx):
    return tv[:idx] + tv[idx+1:]


def mut_drop(tv, rnd: random.Random):
    idx = rnd.choice(range(len(tv)))
    return mut_drop_(tv, idx)


def mut_dup_(tv, idx, shift):
    return mut_shift_(tv + [tv[idx]], len(tv), shift)


def mutate_test_vector(rnd, initial_tv, cnt, debug=False):
    tv_ = initial_tv
    for i in range(cnt):
        coin = rnd.randint(0, 1)
        if coin:
            if debug:
                print("  mutating initial tv")
            tv__ = initial_tv
        else:
            if debug:
                print("  mutating tv_")
            tv__ = tv_
        tv = tv__
        op_kind = rnd.randint(0, 2)
        if op_kind == 0:
            idx = rnd.choice(range(len(tv)))
            if debug:
                print(f"  dropping {idx}")
            tv_ = mut_drop_(tv, idx)
        elif op_kind == 1:
            idx = rnd.choice(range(len(tv)))
            idx_time = tv[idx][0]
            dir = rnd.randint(0, 1)
            if idx_time == 0 or dir:
                time_shift = rnd.randint(0, 6) * 3
            else:
                time_shift = -rnd.randint(0, idx_time // 3) * 3
            if debug:
                print(f"  shifting {idx} by {time_shift}")
            tv_ = mut_shift_(tv, idx, time_shift)
        elif op_kind == 2:
            idx = rnd.choice(range(len(tv)))
            shift = rnd.randint(0, 5) * 3
            if debug:
                print(f"  dupping {idx} and shifting by {shift}")
            tv_ = mut_dup_(tv, idx, shift)
        else:
            assert False
        yield tv_


class MutationOps:
    def __init__(self, start_time, seconds_per_slot, shift_bounds=(-2,4)):
        self.start_time = int(start_time)
        self.seconds_per_slot = int(seconds_per_slot)
        self.shift_bounds = shift_bounds

    def apply_shift(self, tv, idx, delta):
        return mut_shift_(tv, idx, delta)

    def apply_drop(self, tv, idx):
        return mut_drop_(tv, idx)

    def apply_dup_shift(self, tv, idx, delta):
        return mut_dup_(tv, idx, delta)

    def apply_mutation(self, tv, op_kind, *params):
        if op_kind == 'shift':
            return self.apply_shift(tv, *params)
        elif op_kind == 'dup_shift':
            return self.apply_dup_shift(tv, *params)
        elif op_kind == 'drop':
            return self.apply_drop(tv, *params)
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

    def rand_mutation(self, tv, rnd: random.Random):
        idx = rnd.choice(range(len(tv)))
        op_kind = rnd.choice(['shift', 'drop', 'dup_shift'])
        if op_kind == 'shift' or op_kind == 'dup_shift':
            evt_time = int(tv[idx][0])
            params = idx, self.rand_shift(evt_time, rnd)
        else:
            params = idx,
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
