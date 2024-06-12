from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestCasePart
from eth2spec.test.helpers.specs import spec_targets
from eth2spec.test.helpers.fork_choice import (
    on_tick_and_append_step, output_store_checks
)
from eth2spec.utils import bls
from scheduler import MessageScheduler
from instantiators.block_cover import yield_block_cover_test_case
from instantiators.block_tree import yield_block_tree_test_case
from mutation_operators import mutate_test_vector
import random


@dataclass
class FCTestDNA:
    kind: str
    solution: Any
    variation_seed: int
    mutation_seed: Optional[int]


@dataclass(init=False)
class PlainFCTestCase(TestCase):
    test_dna: FCTestDNA
    bls_active: bool
    debug: bool
    def __init__(self, test_dna, bls_active=False, debug=False, **kwds):
        super().__init__(fork_name=kwds['fork_name'], preset_name=kwds['preset_name'],
                         runner_name=kwds['runner_name'], handler_name=kwds['handler_name'],
                         suite_name=kwds['suite_name'], case_name=kwds['case_name'],
                         case_fn=self.mutation_case_fn)
        self.test_dna = test_dna
        self.bls_active = bls_active
        self.debug = debug
    
    def mutation_case_fn(self):
        spec = spec_targets[self.preset_name][self.fork_name]
        base = list(self.plain_case_fn())
        mut_seed = self.test_dna.mutation_seed
        if mut_seed is None:
            return base
        
        rnd = random.Random(mut_seed)
        fc_test_case = parse_test_case(base)
        events = steps_to_events(fc_test_case.steps)
        tv_, = list(mutate_test_vector(rnd, events, 1, debug=self.debug))
        mutated_tc = update_test_case(spec, fc_test_case, tv_)
        #mutated_tc.meta['mutation_seed'] = mut_seed
        return mutated_tc.dump()
    
    def plain_case_fn(self) -> Iterable[TestCasePart]:
        phase, preset = self.fork_name, self.preset_name
        bls_active, debug = self.bls_active, self.debug
        solution, seed = self.test_dna.solution, self.test_dna.variation_seed
        if self.test_dna.kind in ['block_tree_test', 'attester_slashing_test', 'invalid_message_test']:
            with_attester_slashings = self.test_dna.kind == 'attester_slashing_test'
            with_invalid_messages = self.test_dna.kind == 'invalid_message_test'
            return yield_block_tree_test_case(
                generator_mode=True,
                phase=phase, preset=preset,
                bls_active=bls_active, debug=debug,
                seed=seed, sm_links=solution['sm_links'], block_parents=solution['block_parents'],
                with_attester_slashings=with_attester_slashings, with_invalid_messages=with_invalid_messages)
        elif self.test_dna.kind == 'block_cover_test':
            return yield_block_cover_test_case(
                generator_mode=True,
                phase=phase, preset=preset,
                bls_active=bls_active, debug=debug,
                seed=seed, model_params=solution)
        else:
            raise ValueError(f'Unknown FC test kind {self.test_dna.kind}')


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


def update_test_case(spec, fc_test_case: FCTestCase, events):
    old_bls_state = bls.bls_active
    bls.bls_active = False
    try:
        anchor_state = spec.BeaconState.decode_bytes(fc_test_case.anchor_state)
        anchor_block = spec.BeaconBlock.decode_bytes(fc_test_case.anchor_block)
        store = spec.get_forkchoice_store(anchor_state, anchor_block)
        test_steps = []
        scheduler = MessageScheduler(spec, anchor_state, anchor_block)

        for (time, (kind, event)) in events:
            scheduler.process_tick(time)
            on_tick_and_append_step(spec, store, time, test_steps)

            # output checks after applying buffered messages, since they affect store state
            output_store_checks(spec, store, test_steps)

            if kind == 'block':
                block_id = event
                sb = spec.SignedBeaconBlock.decode_bytes(fc_test_case.blocks[block_id])
                valid = scheduler.process_block(sb)
                test_steps.append({'block': block_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attestation':
                att_id = event
                att = spec.Attestation.decode_bytes(fc_test_case.atts[att_id])
                valid = scheduler.process_attestation(att, is_from_block=False)
                test_steps.append({'attestation': att_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attester_slashing':
                slashing_id = event
                slashing = spec.AttesterSlashing.decode_bytes(fc_test_case.slashings[slashing_id])
                valid = scheduler.process_slashing(slashing)
                test_steps.append({'attester_slashing': slashing_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            else:
                raise ValueError(f'not implemented {kind}')
        next_slot_time = store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        # on_tick_and_append_step(spec, store, next_slot_time, test_steps, checks_with_viable_for_head_weights=True)
        on_tick_and_append_step(spec, store, next_slot_time, test_steps)

        return fc_test_case.with_steps(test_steps)
    finally:
        bls.bls_active = old_bls_state


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
