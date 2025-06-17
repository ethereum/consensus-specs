import random
from collections.abc import Iterable
from dataclasses import dataclass
from os import path
from typing import Any
from ruamel.yaml import YAML

from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.test.context import (
    spec_state_test,
    with_altair_and_later,
)
from eth2spec.test.helpers.fork_choice import (
    get_attestation_file_name,
    get_attester_slashing_file_name,
    get_block_file_name,
    on_tick_and_append_step,
    output_store_checks,
)
from eth2spec.utils import bls

from .block_cover import gen_block_cover_test_data
from .block_tree import gen_block_tree_test_data
from .helpers import (
    FCTestData,
    filter_out_duplicate_messages,
    make_events,
    yield_fork_choice_test_events,
)
from .mutation_operators import MutationOps
from .scheduler import MessageScheduler


BLS_ACTIVE = False
GENERATOR_NAME = "fork_choice_compliance"
SUITE_NAME = "pyspec_tests"


@dataclass(eq=True, frozen=True)
class FCTestKind:
    pass


@dataclass(eq=True, frozen=True)
class BlockTreeTestKind(FCTestKind):
    with_attester_slashings: bool
    with_invalid_messages: bool


@dataclass(eq=True, frozen=True)
class BlockCoverTestKind(FCTestKind):
    pass


@dataclass
class FCTestDNA:
    kind: FCTestKind
    solution: Any
    variation_seed: int
    mutation_seed: int | None


@dataclass(init=False)
class PlainFCTestCase(TestCase):
    test_dna: FCTestDNA
    bls_active: bool
    debug: bool

    def __init__(self, test_dna, bls_active=False, debug=False, **kwds):
        super().__init__(
            fork_name=kwds["fork_name"],
            preset_name=kwds["preset_name"],
            runner_name=kwds["runner_name"],
            handler_name=kwds["handler_name"],
            suite_name=kwds["suite_name"],
            case_name=kwds["case_name"],
            case_fn=self.mutation_case_fn,
        )
        self.test_dna = test_dna
        self.bls_active = bls_active
        self.debug = debug

    def mutation_case_fn(self):
        test_kind = self.test_dna.kind
        phase, preset = self.fork_name, self.preset_name
        bls_active, debug = self.bls_active, self.debug
        solution, seed = self.test_dna.solution, self.test_dna.variation_seed
        mut_seed = self.test_dna.mutation_seed
        return yield_mutation_test_case(
            generator_mode=True,
            phase=phase,
            preset=preset,
            bls_active=bls_active,
            debug=debug,
            seed=seed,
            mut_seed=mut_seed,
            test_kind=test_kind,
            solution=solution,
        )


def get_test_data(spec, state, test_kind, solution, debug, seed):
    if isinstance(test_kind, BlockTreeTestKind):
        with_attester_slashings = test_kind.with_attester_slashings
        with_invalid_messages = test_kind.with_invalid_messages
        sm_links = solution["sm_links"]
        block_parents = solution["block_parents"]
        test_data = gen_block_tree_test_data(
            spec,
            state,
            debug,
            seed,
            sm_links,
            block_parents,
            with_attester_slashings,
            with_invalid_messages,
        )
    elif isinstance(test_kind, BlockCoverTestKind):
        model_params = solution
        test_data, _ = gen_block_cover_test_data(spec, state, model_params, debug, seed)
    else:
        raise ValueError(f"Unknown FC test kind {test_kind}")
    return test_data


@with_altair_and_later
@spec_state_test
def yield_mutation_test_case(spec, state, test_kind, solution, debug, seed, mut_seed):
    test_data = get_test_data(spec, state, test_kind, solution, debug, seed)
    events = make_events(spec, test_data)
    store = spec.get_forkchoice_store(test_data.anchor_state, test_data.anchor_block)

    if mut_seed is None:
        return yield_fork_choice_test_events(spec, store, test_data, events, debug)
    else:
        test_vector = events_to_test_vector(events)
        mops = MutationOps(store.time, spec.config.SECONDS_PER_SLOT)
        mutated_vector, mutations = mops.rand_mutations(test_vector, 4, random.Random(mut_seed))

        test_data.meta["mut_seed"] = mut_seed
        test_data.meta["mutations"] = mutations

        mutated_events = test_vector_to_events(mutated_vector)

        return yield_test_parts(spec, store, test_data, mutated_events)


def events_to_test_vector(events) -> list[Any]:
    test_vector = []
    current_time = None
    for event in events:
        event_kind, data, _ = event
        if event_kind == "tick":
            current_time = data
        else:
            if event_kind == "block":
                event_id = data
            elif event_kind == "attestation":
                event_id = data
            elif event_kind == "attester_slashing":
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
            events.append(("tick", time, None))
        events.append((event_kind, data, None))
    return events


@filter_out_duplicate_messages
def yield_test_parts(spec, store, test_data: FCTestData, events):
    record_recovery_messages = True

    for k, v in test_data.meta.items():
        yield k, "meta", v

    yield "anchor_state", test_data.anchor_state
    yield "anchor_block", test_data.anchor_block

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

    for kind, data, _ in events:
        if kind == "tick":
            time = data
            if time > store.time:
                applied_events = scheduler.process_tick(time)
                if record_recovery_messages:
                    for event_kind, event_data, recovery in applied_events:
                        if event_kind == "tick":
                            test_steps.append({"tick": int(event_data)})
                        elif event_kind == "block":
                            assert recovery
                            _block_id = get_block_file_name(event_data)
                            test_steps.append({"block": _block_id, "valid": True})
                        elif event_kind == "attestation":
                            assert recovery
                            _attestation_id = get_attestation_file_name(event_data)
                            if _attestation_id not in test_data.atts:
                                yield _attestation_id, event_data
                            test_steps.append({"attestation": _attestation_id, "valid": True})
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
        elif kind == "block":
            block = data
            block_id = get_block_file_name(block)
            valid, applied_events = scheduler.process_block(block)
            if record_recovery_messages:
                if valid:
                    for event_kind, event_data, recovery in applied_events:
                        if event_kind == "block":
                            _block_id = get_block_file_name(event_data)
                            if recovery:
                                test_steps.append({"block": _block_id, "valid": True})
                            else:
                                test_steps.append({"block": _block_id, "valid": True})
                        elif event_kind == "attestation":
                            _attestation_id = get_attestation_file_name(event_data)
                            if recovery:
                                if _attestation_id not in test_data.atts:
                                    yield _attestation_id, event_data
                                test_steps.append({"attestation": _attestation_id, "valid": True})
                            else:
                                assert False
                                test_steps.append({"attestation": _attestation_id, "valid": True})
                        else:
                            assert False
                else:
                    assert len(applied_events) == 0
                    test_steps.append({"block": block_id, "valid": valid})
            else:
                assert False
                test_steps.append({"block": block_id, "valid": valid})
            block_root = block.message.hash_tree_root()
            assert valid == (block_root in store.blocks)

            output_store_checks(spec, store, test_steps)
        elif kind == "attestation":
            attestation = data
            att_id = get_attestation_file_name(attestation)
            valid = scheduler.process_attestation(attestation, is_from_block=False)
            test_steps.append({"attestation": att_id, "valid": valid})
            output_store_checks(spec, store, test_steps)
        elif kind == "attester_slashing":
            attester_slashing = data
            slashing_id = get_attester_slashing_file_name(attester_slashing)
            valid = scheduler.process_slashing(attester_slashing)
            test_steps.append({"attester_slashing": slashing_id, "valid": valid})
            output_store_checks(spec, store, test_steps)
        else:
            raise ValueError(f"not implemented {kind}")
    next_slot_time = (
        store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
    )
    on_tick_and_append_step(spec, store, next_slot_time, test_steps)
    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)

    yield "steps", test_steps


def prepare_bls():
    bls.use_milagro()


def get_test_kind(test_type, with_attester_slashings, with_invalid_messages):
    if test_type == "block_tree":
        return BlockTreeTestKind(with_attester_slashings, with_invalid_messages)
    elif test_type == "block_cover":
        return BlockCoverTestKind()
    else:
        raise ValueError(f"Unsupported test type: {test_type}")


def _load_yaml(path: str):
    with open(path) as f:
        yaml = YAML(typ="safe")
        return yaml.load(f)


def enumerate_test_dnas(config_dir, test_name, params) -> Iterable[tuple[str, FCTestData]]:
    test_type = params["test_type"]
    instances_path = params["instances"]
    initial_seed = params["seed"]
    nr_variations = params["nr_variations"]
    nr_mutations = params["nr_mutations"]
    with_attester_slashings = params.get("with_attester_slashings", False)
    with_invalid_messages = params.get("with_invalid_messages", False)

    solutions = _load_yaml(path.join(config_dir, instances_path))
    test_kind = get_test_kind(test_type, with_attester_slashings, with_invalid_messages)

    seeds = [initial_seed]
    if nr_variations > 1:
        rnd = random.Random(initial_seed)
        seeds = [rnd.randint(1, 10000) for _ in range(nr_variations)]
        seeds[0] = initial_seed

    for i, solution in enumerate(solutions):
        for seed in seeds:
            for j in range(1 + nr_mutations):
                test_dna = FCTestDNA(test_kind, solution, seed, None if j == 0 else seed + j - 1)
                case_name = test_name + "_" + str(i) + "_" + str(seed) + "_" + str(j)
                yield case_name, test_dna


def enumerate_test_cases(config_path, forks, presets, debug):
    config_dir = path.dirname(config_path)
    test_gen_config = _load_yaml(config_path)

    for test_name, params in test_gen_config.items():
        print(test_name)
        for fork_name in forks:
            for preset_name in presets:
                for case_name, test_dna in enumerate_test_dnas(config_dir, test_name, params):
                    yield PlainFCTestCase(
                        test_dna=test_dna,
                        bls_active=BLS_ACTIVE,
                        debug=debug,
                        fork_name=fork_name,
                        preset_name=preset_name,
                        runner_name=GENERATOR_NAME,
                        handler_name=test_name,
                        suite_name=SUITE_NAME,
                        case_name=case_name,
                    )
