import random


def mut_shift_(tv, idx, delta):
    time, event = tv[idx]
    new_time = int(time) + delta
    if new_time >= 0:
        return sorted(tv[:idx] + [(new_time, event)] + tv[idx+1:], key=lambda x: x[0])


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
