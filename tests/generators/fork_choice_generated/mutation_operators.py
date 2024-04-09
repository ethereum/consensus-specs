from dataclasses import dataclass
from eth2spec.test.helpers.fork_choice import (
    on_tick_and_append_step, output_store_checks
)
from eth2spec.utils import bls
import random


@dataclass
class FCTestCase:
    meta: dict
    anchor_block: object
    anchor_state: object
    blocks: dict
    atts: dict
    slashings: dict
    steps: list

    def with_steps(self, steps):
        return FCTestCase(self.meta, self.anchor_block, self.anchor_state, self.blocks, self.atts, self.slashings, steps)
    
    def dump(self):
        for k,v in self.meta.items():
            yield k, 'meta', v
        yield 'anchor_state', 'ssz', self.anchor_state
        yield 'anchor_block', 'ssz', self.anchor_block
        for k,v in self.blocks.items():
            yield k, 'ssz', v
        for k,v in self.atts.items():
            yield k, 'ssz', v
        for k,v in self.slashings.items():
            yield k, 'ssz', v
        yield 'steps', 'data', self.steps


def parse_test_case(test_case):
    meta = {}
    anchor_block = None
    anchor_state = None
    blocks = {}
    atts = {}
    slashings = {}
    steps = None
    for i, elem in enumerate(test_case):
        assert isinstance(elem, tuple) and len(elem) == 3
        if elem[1] == 'meta':
            meta[elem[0]] = elem[2]
        elif elem[1] == 'ssz':
            if elem[0] == 'anchor_state':
                assert anchor_state is None
                anchor_state = elem[2]
            elif elem[0] == 'anchor_block':
                assert anchor_block is None
                anchor_block = elem[2]
            elif elem[0].startswith('block_'):
                blocks[elem[0]] = elem[2]
            elif elem[0].startswith('attestation_'):
                atts[elem[0]] = elem[2]
            elif elem[0].startswith('attester_slashing_'):
                slashings[elem[0]] = elem[2]
            else:
                raise ValueError(f'not implemented {elem[0]}/{elem[1]}')
        elif elem[1] == 'data' and elem[0] == 'steps':
            assert steps is None
            steps = elem[2]
        else:
            raise ValueError(f'not implemented {elem[0]}/{elem[1]}')
    return FCTestCase(meta, anchor_block, anchor_state, blocks, atts, slashings, steps)
            

def steps_to_events(steps):
    curr = 0
    events = []
    for step in steps:
        if 'tick' in step:
            curr = step['tick']
        elif 'block' in step:
            events.append((curr, ('block', step['block'])))
        elif 'attestation' in step:
            events.append((curr, ('attestation', step['attestation'])))
        elif 'attester_slashing' in step:
            events.append((curr, ('attester_slashing', step['attester_slashing'])))
        elif 'checks' in step or 'property_checks' in step:
            pass
        else:
            assert False, step
    return events


def events_to_steps(events):
    steps = []
    for (time, event) in events:
        steps.append({'tick': int(time)})
        steps.append({event[0]: event[1]})
    return steps


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


def mutate_tc(rnd, initial_tv, cnt, debug=False):
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


def update_test_case(spec, fc_test_case: FCTestCase, events):
    old_bls_state = bls.bls_active
    bls.bls_active = False
    try:
        anchor_state = spec.BeaconState.decode_bytes(fc_test_case.anchor_state)
        anchor_block = spec.BeaconBlock.decode_bytes(fc_test_case.anchor_block)
        store = spec.get_forkchoice_store(anchor_state, anchor_block)
        test_steps = []
        for (time, (kind, event)) in events:
            on_tick_and_append_step(spec, store, time, test_steps)

            if kind == 'block':
                block_id = event
                sb = spec.SignedBeaconBlock.decode_bytes(fc_test_case.blocks[block_id])
                try:
                    spec.on_block(store, sb)
                    for attestation in sb.message.body.attestations:
                        spec.on_attestation(store, attestation, is_from_block=True)

                    for attester_slashing in sb.message.body.attester_slashings:
                        spec.on_attester_slashing(store, attester_slashing)

                    valid = True
                except AssertionError as e:
                    valid = False
                test_steps.append({'block': block_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attestation':
                att_id = event
                att = spec.Attestation.decode_bytes(fc_test_case.atts[att_id])
                try:
                    spec.on_attestation(store, att, is_from_block=False)
                    valid = True
                except AssertionError as e:
                    valid = False
                test_steps.append({'attestation': att_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attester_slashing':
                slashing_id = event
                slashing = spec.AttesterSlashing.decode_bytes(fc_test_case.slashings[slashing_id])
                try:
                    spec.on_attester_slashing(store, slashing)
                    valid = True
                except AssertionError as e:
                    valid = False
                test_steps.append({'attester_slashing': slashing_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            else:
                raise ValueError(f'not implemented {kind}')
        next_slot_time = store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        on_tick_and_append_step(spec, store, next_slot_time, test_steps)

        return fc_test_case.with_steps(test_steps)
    finally:
        bls.bls_active = old_bls_state


def mk_mutations(spec, seed, num, test_fn, debug=False):
    if debug:
        print('make base case')
    base = list(test_fn())
    yield 0, base
    rnd = random.Random(seed)

    fc_test_case = parse_test_case(base)
    events = steps_to_events(fc_test_case.steps)
    for i, tv_ in enumerate(mutate_tc(rnd, events, num, debug=debug)):
        if debug:
            print('make mutant', i+1)
        yield i+1, update_test_case(spec, fc_test_case, tv_).dump()


class MutatorsGenerator:
    def __init__(self, spec, seed, num, test_fn, debug=False):
        self.iterator = iter(mk_mutations(spec, seed, num, test_fn, debug))

    def next_test_case(self):
        _, test_case = next(self.iterator)
        return test_case
