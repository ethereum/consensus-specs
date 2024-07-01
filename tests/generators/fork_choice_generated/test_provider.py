from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase, TestCasePart, TestProvider
from eth2spec.test.context import spec_test
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
from instantiators.helpers import FCTestData, make_events, yield_fork_choice_test_events, filter_out_duplicate_messages
from instantiators.mutation_operators import MutationOps
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
        test_data = list(self.call_instantiator(test_data_only=True))[0][2]
        events = make_events(spec, test_data)
        store = spec.get_forkchoice_store(test_data.anchor_state, test_data.anchor_block)
        start_time = store.time
        seconds_per_slot = spec.config.SECONDS_PER_SLOT

        if mut_seed is None:
            return (spec_test(yield_fork_choice_test_events))(
                spec, store, test_data, events, self.debug, generator_mode=True, bls_active=self.bls_active)
        else:
            test_vector = events_to_test_vector(events)
            mops = MutationOps(start_time, seconds_per_slot)
            mutated_vector, mutations = mops.rand_mutations(test_vector, 4, random.Random(mut_seed))
            
            test_data.meta['mut_seed'] = mut_seed
            test_data.meta['mutations'] = mutations

            mutated_events = test_vector_to_events(mutated_vector)

            # return (spec_test(yield_fork_choice_test_events))(
            #     spec, store, test_data, mutated_events, self.debug, generator_mode=True, bls_active=self.bls_active)
            return (spec_test(yield_test_parts))(
                spec, store, test_data, mutated_events, generator_mode=True, bls_active=self.bls_active)
    
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


@filter_out_duplicate_messages
def yield_test_parts(spec, store, test_data: FCTestData, events):
        record_recovery_messages = True

        for k,v in test_data.meta.items():
            yield k, 'meta', v
        
        yield 'anchor_state', test_data.anchor_state
        yield 'anchor_block', test_data.anchor_block

        for message in test_data.blocks:
            block = message.payload
            yield get_block_file_name(block), block
        
        for message in test_data.atts:
            attestation = message.payload
            yield get_attestation_file_name(attestation), attestation
        
        for message in test_data.slashings:
            attester_slashing = message.payload
            yield get_attester_slashing_file_name(attester_slashing), attester_slashing
        
        test_steps = []
        scheduler = MessageScheduler(spec, store)

        # record first tick
        on_tick_and_append_step(spec, store, store.time, test_steps)

        for (kind, data, _) in events:
            if kind == 'tick':
                time = data
                if time > store.time:
                    applied_events = scheduler.process_tick(time)
                    if record_recovery_messages:
                        for (event_kind, event_data, recovery) in applied_events:
                            if event_kind == 'tick':
                                test_steps.append({'tick': int(event_data)})
                            elif event_kind == 'block':
                                assert recovery
                                _block_id = get_block_file_name(event_data)
                                #print('recovered block', _block_id)
                                test_steps.append({'block': _block_id, 'valid': True}) #, 'recovery': True})
                            elif event_kind == 'attestation':
                                assert recovery
                                _attestation_id = get_attestation_file_name(event_data)
                                if _attestation_id not in test_data.atts:
                                    yield _attestation_id, event_data
                                #print('recovered attestation', _attestation_id)
                                test_steps.append({'attestation': _attestation_id, 'valid': True}) #, 'recovery': True})
                            else:
                                assert False
                    else:
                        assert False
                    if time > store.time:
                        # inside a slot
                        on_tick_and_append_step(spec, store, time, test_steps)
                    else:
                        assert time == store.time
                        output_store_checks(spec, store, test_steps)
            elif kind == 'block':
                block = data
                block_id = get_block_file_name(block)
                valid, applied_events = scheduler.process_block(block)
                if record_recovery_messages:
                    if valid:
                        for (event_kind, event_data, recovery) in applied_events:
                            if event_kind == 'block':
                                _block_id = get_block_file_name(event_data)
                                if recovery:
                                    #print('recovered block', _block_id)
                                    test_steps.append({'block': _block_id, 'valid': True}) #, 'recovery': True})
                                else:
                                    test_steps.append({'block': _block_id, 'valid': True})
                            elif event_kind == 'attestation':
                                _attestation_id = get_attestation_file_name(event_data)
                                if recovery:
                                    #print('recovered attestation', _attestation_id)
                                    if _attestation_id not in test_data.atts:
                                        yield _attestation_id, event_data
                                    test_steps.append({'attestation': _attestation_id, 'valid': True}) #, 'recovery': True})
                                else:
                                    assert False
                                    test_steps.append({'attestation': _attestation_id, 'valid': True})
                            else:
                                assert False
                    else:
                        assert len(applied_events) == 0
                        test_steps.append({'block': block_id, 'valid': valid})
                else:
                    assert False
                    test_steps.append({'block': block_id, 'valid': valid})
                block_root = block.message.hash_tree_root()
                assert valid == (block_root in store.blocks)

                output_store_checks(spec, store, test_steps)
            elif kind == 'attestation':
                attestation = data
                att_id = get_attestation_file_name(attestation)
                valid = scheduler.process_attestation(attestation, is_from_block=False)
                test_steps.append({'attestation': att_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            elif kind == 'attester_slashing':
                attester_slashing = data
                slashing_id = get_attester_slashing_file_name(attester_slashing)
                valid = scheduler.process_slashing(attester_slashing)
                test_steps.append({'attester_slashing': slashing_id, 'valid': valid})
                output_store_checks(spec, store, test_steps)
            else:
                raise ValueError(f'not implemented {kind}')
        next_slot_time = store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        on_tick_and_append_step(spec, store, next_slot_time, test_steps, checks_with_viable_for_head_weights=True)

        yield 'steps', test_steps


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
