from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestCasePart, TestProvider
from eth2spec.test.helpers.specs import spec_targets
from eth2spec.test.helpers.fork_choice import (
    on_tick_and_append_step, output_store_checks,
    get_block_file_name,
    get_attestation_file_name,
    get_attester_slashing_file_name,
)
from eth2spec.test.helpers.typing import SpecForkName, PresetBaseName
from eth2spec.utils import bls
from scheduler import MessageScheduler
from instantiators.block_cover import yield_block_cover_test_case, yield_block_cover_test_data
from instantiators.block_tree import yield_block_tree_test_case, yield_block_tree_test_data
from instantiators.helpers import FCTestData, make_events, yield_fork_choice_test_events
from mutation_operators import mutate_test_vector
import random


BLS_ACTIVE = False
GENERATOR_NAME = 'fork_choice_generated'


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

        mut_seed = self.test_dna.mutation_seed
        if mut_seed is None:
            return list(self.call_instantiator(test_data_only=False))
        else:
            test_data = list(self.call_instantiator(test_data_only=True))[0][2]
            test_vector = events_to_test_vector(make_events(spec, test_data))
            mutated_vector, = list(mutate_test_vector(random.Random(mut_seed), test_vector, 1, debug=self.debug))
            #mutated_tc.meta['mutation_seed'] = mut_seed

            mutated_events = test_vector_to_events(mutated_vector)

            return yield_test_parts(spec, test_data, mutated_vector)
    
    def plain_case_fn(self) -> Iterable[TestCasePart]:
        yield from self.call_instantiator(test_data_only=False)
    
    def call_instantiator(self, test_data_only) -> Iterable[TestCasePart]:
        phase, preset = self.fork_name, self.preset_name
        bls_active, debug = self.bls_active, self.debug
        solution, seed = self.test_dna.solution, self.test_dna.variation_seed
        if self.test_dna.kind in ['block_tree_test', 'attester_slashing_test', 'invalid_message_test']:
            with_attester_slashings = self.test_dna.kind == 'attester_slashing_test'
            with_invalid_messages = self.test_dna.kind == 'invalid_message_test'
            instantiator_fn = yield_block_tree_test_data if test_data_only else yield_block_tree_test_case
            return instantiator_fn(
                generator_mode=True,
                phase=phase, preset=preset,
                bls_active=bls_active, debug=debug,
                seed=seed, sm_links=solution['sm_links'], block_parents=solution['block_parents'],
                with_attester_slashings=with_attester_slashings, with_invalid_messages=with_invalid_messages)
        elif self.test_dna.kind == 'block_cover_test':
            instantiator_fn = yield_block_cover_test_data if test_data_only else yield_block_cover_test_case
            return instantiator_fn(
                generator_mode=True,
                phase=phase, preset=preset,
                bls_active=bls_active, debug=debug,
                seed=seed, model_params=solution)
        else:
            raise ValueError(f'Unknown FC test kind {self.test_dna.kind}')


def events_to_test_vector(events) -> list[Any]:
    test_vector = []
    current_time = None
    for event in events:
        event_kind, data, _  = event
        if event_kind == 'tick':
            current_time = data
        else:
            if event_kind == 'block':
                event_id = data
            elif event_kind == 'attestation':
                event_id = data
            elif event_kind == 'attester_slashing':
                event_id = data
            else:
                assert False, event_kind
            test_vector.append((current_time, (event_kind, event_id)))
    return test_vector


def test_vector_to_events(test_vector):
    events = []
    current_time = None
    for time, (event_kind, data) in test_vector:
        if time != current_time:
            current_time = time
            events.append(('tick', time, None))
        events.append((event_kind, data, None))
    return events


def yield_test_parts(spec, test_data: FCTestData, events):
    old_bls_state = bls.bls_active
    bls.bls_active = False
    try:
        for k,v in test_data.meta.items():
            yield k, 'meta', v
        
        yield 'anchor_state', 'ssz', test_data.anchor_state.encode_bytes()
        yield 'anchor_block', 'ssz', test_data.anchor_block.encode_bytes()

        for message in test_data.blocks:
            block = message.payload
            yield get_block_file_name(block), 'ssz', block.encode_bytes()
        
        for message in test_data.atts:
            attestation = message.payload
            yield get_attestation_file_name(attestation), 'ssz', attestation.encode_bytes()
        
        for message in test_data.slashings:
            attester_slashing = message.payload
            yield get_attester_slashing_file_name(attester_slashing), 'ssz', attester_slashing.encode_bytes()
        
        anchor_state = test_data.anchor_state
        anchor_block = test_data.anchor_block
        store = spec.get_forkchoice_store(anchor_state, anchor_block)
        test_steps = []
        scheduler = MessageScheduler(spec, anchor_state, anchor_block)

        for (time, (kind, event)) in events:
            scheduler.process_tick(time)
            on_tick_and_append_step(spec, store, time, test_steps)

            # output checks after applying buffered messages, since they affect store state
            output_store_checks(spec, store, test_steps)

            if kind == 'block':
                block_id = get_block_file_name(event)
                valid = scheduler.process_block(event)
                test_steps.append({'block': block_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attestation':
                att_id = get_attestation_file_name(event)
                valid = scheduler.process_attestation(event, is_from_block=False)
                test_steps.append({'attestation': att_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attester_slashing':
                slashing_id = get_attester_slashing_file_name(event)
                valid = scheduler.process_slashing(event)
                test_steps.append({'attester_slashing': slashing_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            else:
                raise ValueError(f'not implemented {kind}')
        next_slot_time = store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        # on_tick_and_append_step(spec, store, next_slot_time, test_steps, checks_with_viable_for_head_weights=True)
        on_tick_and_append_step(spec, store, next_slot_time, test_steps)

        yield 'steps', 'data', test_steps
    finally:
        bls.bls_active = old_bls_state


def create_providers(test_name: str, /,
        forks: Iterable[SpecForkName],
        presets: Iterable[PresetBaseName],
        debug: bool,
        initial_seed: int,
        solutions,
        number_of_variations: int,
        number_of_mutations: int,
        test_kind: str,
        ) -> Iterable[TestProvider]:
    def prepare_fn() -> None:
        bls.use_milagro()
        return

    seeds = [initial_seed]
    if number_of_variations > 1:
        rnd = random.Random(initial_seed)
        seeds = [rnd.randint(1, 10000) for _ in range(number_of_variations)]
        seeds[0] = initial_seed
    
    for fork_name in forks:
        for preset_name in presets:
            for i, solution in enumerate(solutions):
                def make_cases_fn() -> Iterable[TestCase]:
                    for seed in seeds:
                        for j in range(1 + number_of_mutations):
                            test_dna = FCTestDNA(test_kind, solution, seed, None if j == 0 else seed + j - 1)
                            yield PlainFCTestCase(
                                test_dna=test_dna,
                                bls_active=BLS_ACTIVE,
                                debug=debug,
                                fork_name=fork_name,
                                preset_name=preset_name,
                                runner_name=GENERATOR_NAME,
                                handler_name=test_name,
                                suite_name='pyspec_tests',
                                case_name=test_name + '_' + str(i) + '_' + str(seed) + '_' + str(j),
                            )

                yield TestProvider(prepare=prepare_fn, make_cases=make_cases_fn)
