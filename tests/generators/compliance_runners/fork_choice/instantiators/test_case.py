import random
from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil
from os import path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.test.context import (
    spec_state_test,
    spec_test,
    with_altair_and_later,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_attestation_file_name,
    get_attester_slashing_file_name,
    get_block_file_name,
    get_execution_payload_envelope_file_name,
    get_payload_attestation_message_file_name,
    on_tick_and_append_step,
    output_store_checks,
)
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.gen_base.gen_typing import (
    TestCase,
    TestCasePart,
    TestCaseResult,
    TestGroup,
)

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
MAX_MUTATION_GROUP_LENGTH = 4


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


@dataclass(eq=True, frozen=True)
class MutationGroupCase:
    case_id: int
    mutation_seed: int | None


@dataclass(eq=True, frozen=True)
class MutationGroup:
    test_name: str
    solution_index: int
    test_dna_base: FCTestDNA
    nr_mutations: int


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
        )
        self.test_dna = test_dna
        self.bls_active = bls_active
        self.debug = debug


@dataclass(init=False)
class MutationGroupTestGroup(TestGroup):
    mutation_group: MutationGroup
    group_cases: tuple[MutationGroupCase, ...]
    fork_name: str
    preset_name: str
    bls_active: bool
    debug: bool

    def __init__(
        self,
        mutation_group,
        group_cases,
        fork_name,
        preset_name,
        bls_active=False,
        debug=False,
    ):
        test_cases = [
            PlainFCTestCase(
                test_dna=test_dna,
                bls_active=bls_active,
                debug=debug,
                fork_name=fork_name,
                preset_name=preset_name,
                runner_name=GENERATOR_NAME,
                handler_name=mutation_group.test_name,
                suite_name=SUITE_NAME,
                case_name=case_name,
            )
            for case_name, test_dna in enumerate_test_dnas(mutation_group, group_cases)
        ]
        super().__init__(
            group_name=(
                f"{preset_name}::{fork_name}::{GENERATOR_NAME}::"
                f"{mutation_group.test_name}::{mutation_group.solution_index}::"
                f"{mutation_group.test_dna_base.variation_seed}"
                f"{get_mutation_group_suffix(mutation_group.nr_mutations, group_cases)}"
            ),
            test_cases=test_cases,
            group_fn=self.execute_group,
        )
        self.mutation_group = mutation_group
        self.group_cases = group_cases
        self.fork_name = fork_name
        self.preset_name = preset_name
        self.bls_active = bls_active
        self.debug = debug

    def execute_group(self) -> Iterable[TestCaseResult]:
        bls_active = self.bls_active
        debug = self.debug

        spec, test_data, events = make_test_context(
            self.mutation_group.test_dna_base,
            self.fork_name,
            self.preset_name,
            bls_active=bls_active,
            debug=debug,
        )

        for test_case in self.test_cases:
            mut_seed = test_case.test_dna.mutation_seed
            if mut_seed is None:
                parts_iter = yield_fork_choice_test_events(
                    spec, test_data, events, debug, bls_active=bls_active
                )
            else:
                parts_iter = yield_mutated_test_case_parts(
                    spec, test_data, events, mut_seed, bls_active=bls_active
                )

            yield collect_test_case_result_from_iterator(test_case, parts_iter)


def collect_test_case_result_from_iterator(
    test_case: TestCase,
    parts_iter: Iterable[TestCasePart],
) -> TestCaseResult:
    meta: dict[str, Any] = {}
    outputs: list[TestCasePart] = []

    for name, kind, data in parts_iter:
        if kind == "meta":
            meta[name] = data
        else:
            outputs.append(TestCasePart((name, kind, data)))

    return TestCaseResult(test_case=test_case, meta=meta, case_parts=outputs)


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


def make_test_context(
    test_dna_base: FCTestDNA,
    fork_name: str,
    preset_name: str,
    bls_active: bool = False,
    debug: bool = False,
):
    @with_altair_and_later
    @spec_state_test
    def get_spec_test_data_and_events(spec, state):
        test_kind = test_dna_base.kind
        solution = test_dna_base.solution
        seed = test_dna_base.variation_seed
        test_data = get_test_data(spec, state, test_kind, solution, debug, seed)
        events = make_events(spec, test_data)
        yield (spec, test_data, events)

    ((spec, test_data, events),) = get_spec_test_data_and_events(
        phase=fork_name,
        preset=preset_name,
        bls_active=bls_active,
    )

    return spec, test_data, events


@spec_test
def yield_mutated_test_case_parts(spec, test_data, events, mut_seed):
    store = spec.get_forkchoice_store(test_data.anchor_state, test_data.anchor_block)

    test_vector = events_to_test_vector(events)
    mops = MutationOps(store.time, spec.config.SLOT_DURATION_MS // 1000)
    mutated_vector, mutations = mops.rand_mutations(test_vector, 4, random.Random(mut_seed))

    test_data.meta["mut_seed"] = mut_seed
    test_data.meta["mutations"] = mutations

    mutated_events = convert_test_vector_to_events(mutated_vector)
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
            elif event_kind == "execution_payload":
                event_id = data
            elif event_kind == "payload_attestation":
                event_id = data
            else:
                assert False, event_kind
            test_vector.append((current_time, (event_kind, event_id)))
    return test_vector


def convert_test_vector_to_events(test_vector):
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

    for message in test_data.envelopes:
        envelope = message.payload
        yield get_execution_payload_envelope_file_name(envelope), envelope

    for message in test_data.payload_atts:
        ptc_message = message.payload
        yield get_payload_attestation_message_file_name(ptc_message), ptc_message

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
                        elif event_kind == "execution_payload":
                            assert recovery
                            _payload_id = get_execution_payload_envelope_file_name(event_data)
                            test_steps.append({"execution_payload": _payload_id, "valid": True})
                        elif event_kind == "payload_attestation":
                            assert recovery
                            _payload_attestation_id = get_payload_attestation_message_file_name(
                                event_data
                            )
                            test_steps.append(
                                {"payload_attestation": _payload_attestation_id, "valid": True}
                            )
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
                        elif event_kind == "execution_payload":
                            assert recovery
                            _payload_id = get_execution_payload_envelope_file_name(event_data)
                            test_steps.append({"execution_payload": _payload_id, "valid": True})
                        elif event_kind == "payload_attestation":
                            _payload_attestation_id = get_payload_attestation_message_file_name(
                                event_data
                            )
                            assert recovery
                            test_steps.append(
                                {"payload_attestation": _payload_attestation_id, "valid": True}
                            )
                        else:
                            assert False
                else:
                    assert len(applied_events) == 0
                    test_steps.append({"block": block_id, "valid": valid})
            else:
                assert False
                test_steps.append({"block": block_id, "valid": valid})
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
        elif kind == "execution_payload":
            envelope = data
            envelope_id = get_execution_payload_envelope_file_name(envelope)
            valid = scheduler.process_payload(envelope)
            test_steps.append({"execution_payload": envelope_id, "valid": valid})
            output_store_checks(spec, store, test_steps)
        elif kind == "payload_attestation":
            ptc_message = data
            ptc_message_id = get_payload_attestation_message_file_name(ptc_message)
            valid = scheduler.process_payload_attestation_message(ptc_message, is_from_block=False)
            test_steps.append({"payload_attestation": ptc_message_id, "valid": valid})
            output_store_checks(spec, store, test_steps)
        else:
            raise ValueError(f"not implemented {kind}")
    next_slot_time = (
        store.genesis_time
        + (spec.get_current_slot(store) + 1) * spec.config.SLOT_DURATION_MS // 1000
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


def derive_effective_seed(seed: int, solution_index: int) -> int:
    return random.Random(f"{seed}:{solution_index}").randint(0, 1_000_000_000)


def get_mutation_group_suffix(nr_mutations: int, group_cases: tuple[MutationGroupCase, ...]) -> str:
    group_case_ids = [group_case.case_id for group_case in group_cases]
    full_case_ids = list(range(0, nr_mutations + 1))
    if group_case_ids == full_case_ids:
        return ""
    joined_case_ids = ",".join(str(case_id) for case_id in group_case_ids)
    return f"::cases={joined_case_ids}"


def iter_mutation_group_chunks(
    mutation_seeds: list[int],
) -> Iterable[tuple[MutationGroupCase, ...]]:
    all_group_cases = [MutationGroupCase(0, None)] + [
        MutationGroupCase(case_id=i, mutation_seed=mutation_seed)
        for i, mutation_seed in enumerate(mutation_seeds, start=1)
    ]
    total_group_length = len(all_group_cases)
    if total_group_length <= MAX_MUTATION_GROUP_LENGTH:
        yield tuple(all_group_cases)
        return

    bucket_count = ceil(total_group_length / MAX_MUTATION_GROUP_LENGTH)
    base_bucket_size = total_group_length // bucket_count
    remainder = total_group_length % bucket_count
    bucket_sizes = [
        base_bucket_size + (1 if bucket_index < remainder else 0)
        for bucket_index in range(bucket_count)
    ]

    remaining_mutation_cases = all_group_cases[1:]
    for bucket_index, bucket_size in enumerate(bucket_sizes):
        if bucket_index == 0:
            mutations_in_bucket = bucket_size - 1
            bucket_cases = remaining_mutation_cases[:mutations_in_bucket]
            yield (all_group_cases[0], *bucket_cases)
        else:
            mutations_in_bucket = bucket_size
            bucket_cases = remaining_mutation_cases[:mutations_in_bucket]
            yield tuple(bucket_cases)
        remaining_mutation_cases = remaining_mutation_cases[mutations_in_bucket:]


def enumerate_mutation_groups(config_dir, test_name, params) -> Iterable[MutationGroup]:
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
            effective_seed = derive_effective_seed(seed, i)
            yield MutationGroup(
                test_name=test_name,
                solution_index=i,
                test_dna_base=FCTestDNA(test_kind, solution, effective_seed, None),
                nr_mutations=nr_mutations,
            )


def split_mutation_group(mutation_group: MutationGroup) -> Iterable[tuple[MutationGroupCase, ...]]:
    mutation_seeds = [
        mutation_group.test_dna_base.variation_seed + j - 1
        for j in range(1, mutation_group.nr_mutations + 1)
    ]
    yield from iter_mutation_group_chunks(mutation_seeds)


def enumerate_test_dnas(
    mutation_group: MutationGroup, group_cases: tuple[MutationGroupCase, ...]
) -> Iterable[tuple[str, FCTestDNA]]:
    test_name = mutation_group.test_name
    solution_index = mutation_group.solution_index
    test_dna_base = mutation_group.test_dna_base
    seed = test_dna_base.variation_seed

    for group_case in group_cases:
        case_id = group_case.case_id
        mutation_seed = group_case.mutation_seed
        test_dna = FCTestDNA(
            test_dna_base.kind,
            test_dna_base.solution,
            seed,
            mutation_seed,
        )
        case_name = test_name + "_" + str(solution_index) + "_" + str(seed) + "_" + str(case_id)
        yield case_name, test_dna


def enumerate_test_groups(config_path, forks, presets, debug, initial_seed: int = None):
    config_dir = path.dirname(config_path)
    test_gen_config = _load_yaml(config_path)

    seed_generator = random.Random(initial_seed) if initial_seed is not None else None
    for test_name, params in test_gen_config.items():
        if seed_generator is not None:
            params = params | {"seed": seed_generator.randint(0, 1_000_000_000)}
        if debug:
            print(test_name)
        for fork_name in forks:
            for preset_name in presets:
                for mutation_group in enumerate_mutation_groups(config_dir, test_name, params):
                    for group_cases in split_mutation_group(mutation_group):
                        yield MutationGroupTestGroup(
                            mutation_group=mutation_group,
                            group_cases=group_cases,
                            fork_name=fork_name,
                            preset_name=preset_name,
                            bls_active=BLS_ACTIVE,
                            debug=debug,
                        )
