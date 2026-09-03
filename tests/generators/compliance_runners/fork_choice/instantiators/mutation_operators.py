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


def mut_equivocation_delay_(tv, idxs, new_time):
    # Move every copy of the targeted block to `new_time`. All copies must move
    # together: block timeliness is recorded at first import, so a single
    # remaining on-time copy would keep the block timely.
    idxs = set(idxs)
    kept = [entry for i, entry in enumerate(tv) if i not in idxs]
    delayed = [(new_time, tv[i][1]) for i in idxs]
    return sorted(kept + delayed, key=lambda x: x[0])


class MutationOps:
    """
    Random mutations for fork-choice event vectors.

    The active mutation set is:
    - ``shift``: move one event earlier or later in time
    - ``late_arrival``: remove an event from its original position and reinsert it
      near the tail of the test vector
    - ``multi_route``: keep the original event and add one or more shifted copies,
      modeling delivery through multiple routes
    - ``equivocation_delay``: delay one block of a same-slot same-proposer pair
      to a random point in its own or the following slot. Untargeted mutations
      almost never move an equivocating sibling, so timeliness-sensitive logic
      keyed on equivocations (e.g. `should_apply_proposer_boost`) only ever sees
      siblings delivered at their slot start without this operator
    """

    def __init__(
        self,
        start_time,
        seconds_per_slot,
        shift_bounds=(-2, 4),
        genesis_time=None,
    ):
        self.start_time = int(start_time)
        self.seconds_per_slot = int(seconds_per_slot)
        self.shift_bounds = shift_bounds
        self.genesis_time = None if genesis_time is None else int(genesis_time)

    def apply_shift(self, tv, idx, delta):
        return mut_shift_(tv, idx, delta)

    def apply_late_arrival(self, tv, idx, new_time):
        return mut_late_arrival_(tv, idx, new_time)

    def apply_multi_route(self, tv, idx, deltas):
        return mut_multi_route_(tv, idx, deltas)

    def apply_equivocation_delay(self, tv, idxs, new_time):
        return mut_equivocation_delay_(tv, idxs, new_time)

    def apply_mutation(self, tv, op_kind, *params):
        if op_kind == "shift":
            return self.apply_shift(tv, *params)
        elif op_kind == "late_arrival":
            return self.apply_late_arrival(tv, *params)
        elif op_kind == "multi_route":
            return self.apply_multi_route(tv, *params)
        elif op_kind == "equivocation_delay":
            return self.apply_equivocation_delay(tv, *params)
        else:
            raise AssertionError

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

    def rand_event_index(self, tv, rnd: random.Random) -> int:
        # Bias mutations toward later events to preserve more of the early
        # scenario setup and reduce accidental truncation.
        return rnd.choices(range(len(tv)), weights=range(1, len(tv) + 1), k=1)[0]

    def equivocating_block_groups(self, tv):
        """
        Group block event indices by (slot, proposer_index), keeping only groups
        that contain two or more distinct blocks, i.e. proposer equivocations.
        Returns a list of groups; each group maps a block root to the indices of
        all its copies in the test vector.
        """
        by_slot_proposer = {}
        for i, (_, event) in enumerate(tv):
            event_kind, data = event
            if event_kind != "block":
                continue
            block = data.message
            key = int(block.slot), int(block.proposer_index)
            by_slot_proposer.setdefault(key, {}).setdefault(block.hash_tree_root(), []).append(i)
        return [group for group in by_slot_proposer.values() if len(group) > 1]

    def rand_equivocation_delay_time(self, block_slot: int, rnd: random.Random) -> int:
        # Deliver the block at a random whole second within its own slot or the
        # following one. This straddles the intra-slot timeliness deadlines, so
        # over many seeds the delayed sibling lands on both sides of each one.
        # A delay of 0 keeps the block at its slot start; when composed after
        # another mutation of the same block, it restores baseline delivery.
        slot_start = self.genesis_time + block_slot * self.seconds_per_slot
        return slot_start + rnd.randint(0, 2 * self.seconds_per_slot)

    def rand_operator_kind(self, event_kind: str, rnd: random.Random) -> str:
        if event_kind == "block":
            choices = ["shift", "late_arrival", "multi_route"]
            weights = [5, 1, 3]
            if self.genesis_time is not None:
                # equivocation_delay is a targeted shift, so its weight is carved
                # out of shift's share rather than added on top. Vectors without
                # equivocations fall back to shift, restoring the original [5, 1, 3].
                choices.append("equivocation_delay")
                weights = [2, 1, 3, 3]
        elif event_kind in ("attestation", "payload_attestation"):
            choices = ["shift", "late_arrival", "multi_route"]
            weights = [2, 3, 4]
        elif event_kind == "execution_payload":
            choices = ["shift", "late_arrival", "multi_route"]
            weights = [2, 4, 3]
        else:
            assert event_kind == "attester_slashing"
            choices = ["shift", "late_arrival", "multi_route"]
            weights = [4, 3, 1]

        return rnd.choices(choices, weights=weights, k=1)[0]

    def rand_mutation(self, tv, rnd: random.Random):
        idx = self.rand_event_index(tv, rnd)
        event_kind = tv[idx][1][0]
        op_kind = self.rand_operator_kind(event_kind, rnd)
        if op_kind == "equivocation_delay":
            groups = self.equivocating_block_groups(tv)
            if len(groups) == 0:
                # No proposer equivocation in this vector; fall back to a shift.
                op_kind = "shift"
            else:
                # Prefer the group containing the picked event, otherwise pick one
                # at random, then delay one of the group's blocks.
                containing = [g for g in groups if any(idx in idxs for idxs in g.values())]
                group = containing[0] if containing else rnd.choice(groups)
                root = rnd.choice(sorted(group))
                idxs = tuple(group[root])
                block_slot = int(tv[idxs[0]][1][1].message.slot)
                params = idxs, self.rand_equivocation_delay_time(block_slot, rnd)
                return op_kind, *params
        if op_kind == "shift":
            evt_time = int(tv[idx][0])
            params = idx, self.rand_shift(evt_time, rnd)
        elif op_kind == "late_arrival":
            params = idx, self.rand_late_arrival_time(tv, rnd)
        elif op_kind == "multi_route":
            evt_time = int(tv[idx][0])
            params = idx, self.rand_multi_route_shifts(evt_time, rnd)
        else:
            raise AssertionError
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
