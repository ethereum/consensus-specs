from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace
from random import Random

from eth_utils import encode_hex

from eth2spec.test.helpers.attestations import (
    get_valid_attestations_for_block_at_slot,
)
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
)
from eth2spec.test.helpers.fork_choice import (
    add_attester_slashing,
    add_block,
    get_attestation_file_name,
    get_basic_store_checks,
    get_genesis_forkchoice_store_and_block,
)
from eth2spec.test.helpers.forks import (
    is_post_electra,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)

DEBUG = False


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def output_fast_confirmation_checks(spec, store, test_steps):
    basic_checks = get_basic_store_checks(spec, store)
    fcr_checks = {
        "previous_epoch_observed_justified_checkpoint": {
            "epoch": int(store.previous_epoch_observed_justified_checkpoint.epoch),
            "root": encode_hex(store.previous_epoch_observed_justified_checkpoint.root),
        },
        "current_epoch_observed_justified_checkpoint": {
            "epoch": int(store.current_epoch_observed_justified_checkpoint.epoch),
            "root": encode_hex(store.current_epoch_observed_justified_checkpoint.root),
        },
        "previous_epoch_greatest_unrealized_checkpoint": {
            "epoch": int(store.previous_epoch_greatest_unrealized_checkpoint.epoch),
            "root": encode_hex(store.previous_epoch_greatest_unrealized_checkpoint.root),
        },
        "previous_slot_head": encode_hex(store.previous_slot_head),
        "current_slot_head": encode_hex(store.current_slot_head),
        "confirmed_root": encode_hex(store.confirmed_root),
    }
    test_steps.append({"checks": basic_checks | fcr_checks})


def on_fast_confirmation_and_append_step(spec, store, test_steps):
    spec.on_fast_confirmation(store)
    output_fast_confirmation_checks(spec, store, test_steps)


def str_to_graffiti(graffiti: str) -> bytes:
    return bytes(graffiti, "ascii").ljust(32, b"\x00")


def graffiti_to_str(graffiti: bytes) -> str:
    return graffiti.rstrip(b"\x00").decode("ascii")


class FCRTest:
    def __init__(self, spec, seed):
        self.spec = spec
        self.seed = seed

    def initialize(self, anchor_state):
        # Initialization
        test_steps = []
        store, anchor_block = get_genesis_forkchoice_store_and_block(self.spec, anchor_state)

        self.rng = Random(self.seed)
        self.store = store
        self.test_steps = test_steps
        self.attestation_pool = []
        self.recent_attestations = []
        self.blockchain_artefacts = []

        # Tick
        self.tick(self.spec.GENESIS_SLOT)

        self.blockchain_artefacts.append(("anchor_state", anchor_state))
        self.blockchain_artefacts.append(("anchor_block", anchor_block))

        return store

    def get_test_artefacts(self):
        return self.blockchain_artefacts + [("steps", self.test_steps)]

    def current_slot(self):
        return self.spec.get_current_slot(self.store)

    def current_epoch(self):
        return self.spec.get_current_store_epoch(self.store)

    def head(self):
        return self.spec.get_head(self.store)

    def get_parent(self, block_root):
        parent_root = self.store.blocks[block_root].parent_root
        return self.store.blocks[parent_root]

    def get_children(self, block_root):
        return [
            root
            for root in self.store.blocks.keys()
            if self.store.blocks[root].parent_root == block_root
        ]

    def find_block_root(self, predicate: Callable[[object], bool]) -> object:
        for root, block in self.store.blocks.items():
            if predicate(block):
                return root

        raise KeyError("Block not found")

    def resolve_slot_by_offset(self, offset_or_slot):
        if offset_or_slot > 0:
            return self.spec.Slot(offset_or_slot)
        else:
            return self.spec.Slot(int(self.current_slot()) + offset_or_slot)

    def get_block_root_or_head(self, block_root_id):
        if block_root_id == None:
            return self.head()

        if isinstance(block_root_id, int):
            # Slot or offset
            slot = self.resolve_slot_by_offset(block_root_id)
            return self.find_block_root(lambda b: b.slot == slot)
        elif isinstance(block_root_id, str):
            # Graffiti
            graffiti = str_to_graffiti(block_root_id)
            return self.find_block_root(lambda b: b.body.graffiti == graffiti)
        else:
            # Block root
            return block_root_id

    def get_supporters_of(self, block_root_id) -> list[object]:
        block_root = self.get_block_root_or_head(block_root_id)
        return [i for i, m in self.store.latest_messages.items() if m.root == block_root]

    def tick(self, slot):
        assert slot > self.current_slot() or slot == self.spec.GENESIS_SLOT
        new_time = slot * self.spec.config.SECONDS_PER_SLOT + self.store.genesis_time
        self.spec.on_tick(self.store, new_time)
        self.test_steps.append({"tick": int(new_time)})

    def next_slot(self):
        self.tick(self.current_slot() + 1)

        # Discard outdated attestations from the pool
        if self.current_slot() % self.spec.SLOTS_PER_EPOCH == 0:
            self.attestation_pool = [
                a
                for a in self.attestation_pool
                if self.spec.compute_epoch_at_slot(a.data.slot) + 1 >= self.current_epoch()
            ]

        # Apply recent attestations
        self.apply_attestations(self.recent_attestations)
        self.recent_attestations = []

    def max_attestations(self):
        if is_post_electra(self.spec):
            return self.spec.MAX_ATTESTATIONS_ELECTRA
        else:
            return self.spec.MAX_ATTESTATIONS

    def add_and_apply_block(
        self,
        parent_root=None,
        release_att_pool=True,
        graffiti: str = None,
        include_atts=True,
        attestations=None,
        include_att_fn: Callable[[object, object], bool] = None,
    ):
        if parent_root is None:
            parent_root = self.head()
        else:
            assert parent_root in self.store.blocks

        current_slot = self.current_slot()

        # Return anchor_block root for GENESIS_SLOT
        if current_slot == self.spec.GENESIS_SLOT:
            return self.store.finalized_checkpoint.root

        parent_state = self.store.block_states[parent_root].copy()
        assert parent_state.slot < current_slot

        # Build a block for current_slot with attestations from pool
        # build_empty_block will advance the state to current_slot if necessary
        block = build_empty_block(self.spec, parent_state, current_slot)

        if graffiti is not None:
            block.body.graffiti = str_to_graffiti(graffiti)

        if attestations is not None:
            for att in attestations[: self.max_attestations()]:
                block.body.attestations.append(att)
        elif include_atts:
            for att in self.attestation_pool:
                if att.data.slot + self.spec.MIN_ATTESTATION_INCLUSION_DELAY > block.slot:
                    continue

                if is_post_electra(self.spec):
                    if self.spec.compute_epoch_at_slot(
                        att.data.slot
                    ) + 1 < self.spec.compute_epoch_at_slot(block.slot):
                        continue
                elif att.data.slot + self.spec.SLOTS_PER_EPOCH < block.slot:
                    continue

                if include_att_fn == None or include_att_fn(block, att):
                    block.body.attestations.append(att)

                if len(block.body.attestations) >= self.max_attestations():
                    break

            # Release included attestations from the pool
            if release_att_pool:
                included_atts = set(block.body.attestations)
                self.attestation_pool = [
                    att for att in self.attestation_pool if att not in included_atts
                ]

        # Sign block and add it to the Store
        signed_block = state_transition_and_sign_block(self.spec, parent_state, block)
        for artefact in add_block(self.spec, self.store, signed_block, self.test_steps):
            self.blockchain_artefacts.append(artefact)

        return self.spec.Root(block.hash_tree_root())

    def attest(self, block_root=None, slot=None, participation_rate=100, pool_and_disseminate=True):
        assert 0 <= participation_rate <= 100

        # Do not attest if participation is zero
        if participation_rate == 0:
            return []

        if block_root is None:
            block_root = self.head()
        else:
            assert block_root in self.store.blocks

        if slot is None:
            slot = self.current_slot()

        att_state = self.store.block_states[block_root].copy()

        # Advance state if needed
        transition_to(self.spec, att_state, slot)

        # Prevent attesting if slot is incorrect
        # or too old such that committee shuffling would be incorrect
        assert slot >= att_state.slot
        assert self.spec.get_current_epoch(att_state) == self.spec.compute_epoch_at_slot(slot)

        # Sample active validators
        if participation_rate < 100:
            active_set = self.sample_fraction_of_participants(att_state, slot, participation_rate)
        else:
            active_set = None

        # Attest and add attestations to the pool
        attestations = get_valid_attestations_for_block_at_slot(
            self.spec,
            att_state,
            slot,
            block_root,
            participation_fn=(
                lambda slot, index, committee: committee & active_set
                if active_set != None
                else committee
            ),
        )
        if pool_and_disseminate:
            self.attestation_pool.extend(attestations)
            self.recent_attestations.extend(attestations)

            # Yield test data
            for attestation in attestations:
                att_tuple = (get_attestation_file_name(attestation), attestation)
                self.blockchain_artefacts.append(att_tuple)
                self.test_steps.append({"attestation": att_tuple[0]})

        return attestations

    def apply_attestations(self, attestations):
        # Apply attestations to the fork choice
        for attestation in attestations:
            self.spec.on_attestation(self.store, attestation, is_from_block=False)

    def run_fast_confirmation(self):
        on_fast_confirmation_and_append_step(self.spec, self.store, self.test_steps)

    def next_slot_with_block(
        self,
        participation_rate=100,
        parent_root=None,
        graffiti=None,
        release_att_pool=True,
        include_atts=True,
    ):
        block_root = self.add_and_apply_block(
            parent_root=parent_root,
            graffiti=graffiti,
            release_att_pool=release_att_pool,
            include_atts=include_atts,
        )
        self.attest(
            block_root=self.head(), slot=self.current_slot(), participation_rate=participation_rate
        )
        self.next_slot()
        return block_root

    def next_slot_with_block_and_fast_confirmation(
        self,
        participation_rate=100,
        parent_root=None,
        graffiti=None,
        release_att_pool=True,
        include_atts=True,
    ):
        block_root = self.next_slot_with_block(
            participation_rate, parent_root, graffiti, release_att_pool, include_atts
        )
        self.run_fast_confirmation()
        return block_root

    def attest_and_next_slot_with_fast_confirmation(
        self, block_root=None, slot=None, participation_rate=100
    ):
        self.attest(block_root, slot, participation_rate)
        self.next_slot()
        self.run_fast_confirmation()

    def run_slots_with_blocks_and_fast_confirmation(self, number_of_slots, participation_rate=100):
        for _ in range(number_of_slots):
            self.next_slot_with_block_and_fast_confirmation(participation_rate)

    def get_slot_committee(self, shuffling_source, slot):
        committees_count = self.spec.get_committee_count_per_slot(
            shuffling_source, self.spec.compute_epoch_at_slot(slot)
        )
        committee: list[self.spec.ValidatorIndex] = list()
        for i in range(committees_count):
            committee.extend(
                self.spec.get_beacon_committee(
                    shuffling_source, self.spec.Slot(slot), self.spec.CommitteeIndex(i)
                )
            )
        return committee

    def sample_fraction_of_participants(self, shuffling_source, slot, fraction):
        slot_committee = self.get_slot_committee(shuffling_source, slot)
        participants_count = len(slot_committee) * fraction // 100
        self.rng.shuffle(slot_committee)
        return set(slot_committee[:participants_count])

    def apply_attester_slashing(
        self, slashing_percentage: int = None, slashing_indices: list[int] = None, slot=None
    ) -> list[object]:
        if slot is None:
            slot = self.current_slot()
        state = self.store.block_states[self.head()].copy()
        if slashing_indices is None:
            assert slashing_percentage is not None
            slashing_count = len(state.validators) * slashing_percentage // 100
            unslashed_indices = [idx for idx, val in enumerate(state.validators) if not val.slashed]
            self.rng.shuffle(unslashed_indices)
            slashing_indices = unslashed_indices[:slashing_count]
        else:
            assert len(slashing_indices) > 0

        transition_to(self.spec, state, slot)

        attester_slashing = get_valid_attester_slashing_by_indices(
            self.spec, state, sorted(slashing_indices), slot=slot, signed_1=True, signed_2=True
        )

        for artefact in add_attester_slashing(
            self.spec, self.store, attester_slashing, self.test_steps
        ):
            self.blockchain_artefacts.append(artefact)

        return attester_slashing

    def compute_score_and_threshold(self, block_root) -> (int, int):
        balance_source = self.spec.get_current_balance_source(self.store)
        score = self.spec.get_attestation_score(self.store, block_root, balance_source)
        safety_threshold = self.spec.compute_safety_threshold(
            self.store, block_root, balance_source
        )
        return int(score), int(safety_threshold)

    def get_slot_root_info(self, block_root):
        if block_root == self.spec.Root():
            slot = self.spec.GENESIS_SLOT
            graffiti = "genesis"
        else:
            block = self.store.blocks[block_root]
            slot = block.slot
            graffiti = graffiti_to_str(block.body.graffiti)

        if len(graffiti) > 0:
            return f"{slot}: {str(block_root)[:6]}, '{graffiti}'"
        else:
            return f"{slot}: {str(block_root)[:6]}"

    def get_checkpoint_info(self, checkpoint):
        return f"{checkpoint.epoch}: {str(checkpoint.root)[:6]}"

    def print_fast_confirmed_block_tree(self, start_root):
        if not DEBUG:
            return

        spec = self.spec
        store = self.store

        balance_source = spec.get_current_balance_source(store)
        total_active_balance = spec.get_total_active_balance(balance_source)
        one_committee_weight = int(total_active_balance // spec.SLOTS_PER_EPOCH)

        def get_relative_score_and_threshold(block_root):
            score, threshold = self.compute_score_and_threshold(block_root)
            return score * 100 / one_committee_weight, threshold * 100 / one_committee_weight

        def get_one_confirmed_info(block_root):
            # Genesis block
            if spec.get_block_slot(store, block_root) == spec.GENESIS_SLOT:
                genesis_info = self.get_slot_root_info(block_root)
                if block_root == store.confirmed_root:
                    return f"\033[94m({genesis_info})\033[0m"
                else:
                    return f"\033[92m({genesis_info})\033[0m"

            score, threshold = get_relative_score_and_threshold(block_root)
            output = f"({self.get_slot_root_info(block_root)}, uj={store.unrealized_justifications[block_root].epoch}, sc={score:.1f}%, th={threshold:.1f}%)"

            if block_root == store.confirmed_root:
                # Confirmed block in Blue if can be re-confirmed, Magenta otherwise
                if score > threshold:
                    return f"\033[94m{output}\033[0m"
                else:
                    return f"\033[95m{output}\033[0m"

            # Other blocks in either green or red depending on whether they can be one_confirmed
            if score > threshold:
                return f"\033[92m{output}\033[0m"
            else:
                return f"\033[91m{output}\033[0m"

        block_infos = []
        block_root = start_root
        while True:
            block_infos.append(get_one_confirmed_info(block_root))
            children = self.get_children(block_root)

            # Continue accumulating if we are on a single branch with more blocks on it
            if len(children) == 1:
                block_root = children[0]
                continue

            # Print accumulated output if not
            print(
                f"parent({self.get_slot_root_info(store.blocks[start_root].parent_root)}): {', '.join(block_infos)}"
            )

            # Print subtrees if there are any
            for root in children:
                self.print_fast_confirmed_block_tree(root)

            # Exit
            break

    def print_fast_confirmation_state(self):
        if not DEBUG:
            return

        spec = self.spec
        store = self.store

        # Print epoch and slot
        print(
            f"\nEpoch {self.current_epoch()}, Slot {self.current_slot() % self.spec.SLOTS_PER_EPOCH}:"
        )

        # Print block tree starting from the beginning of previous epoch
        if self.current_epoch() == spec.GENESIS_EPOCH:
            start_slot = spec.GENESIS_SLOT
        else:
            start_slot = spec.compute_start_slot_at_epoch(self.current_epoch() - 1)
        start_root = spec.get_ancestor(store, self.head(), start_slot)
        self.print_fast_confirmed_block_tree(start_root)

        # Print head variables
        def get_head_info(head_root):
            vs = spec.get_voting_source(store, head_root)
            uj = store.unrealized_justifications[head_root]
            return f"{self.get_slot_root_info(head_root)}, vs=({self.get_checkpoint_info(vs)}), uj=({self.get_checkpoint_info(uj)})"

        print(f"\nprev_head [{get_head_info(store.previous_slot_head)}]")
        print(f"curr_head [{get_head_info(store.current_slot_head)}]")
        print(f"head      [{get_head_info(self.head())}]")

        # Print prev epoch GU and current target
        curr_target = spec.get_current_target(store)
        balance_source = spec.get_pulled_up_head_state(store)
        total_active_balance = spec.get_total_active_balance(balance_source)
        ffg_support = spec.compute_honest_ffg_support_for_current_target(store)
        relative_support = int(ffg_support) * 100 / int(total_active_balance)

        print(
            f"\ncurr_target [{self.get_checkpoint_info(curr_target)}, ffg_support={relative_support:.1f}%]"
        )
        print(
            f"prev_epoch_gu [{self.get_checkpoint_info(store.previous_epoch_greatest_unrealized_checkpoint)}]"
        )
        print(f"justified_checkpoint [{self.get_checkpoint_info(store.justified_checkpoint)}]")
        print(f"finalized_checkpoint [{self.get_checkpoint_info(store.finalized_checkpoint)}]")


@dataclass
class SystemRun:
    def execute(self, fcr: FCRTest) -> object:
        pass

    def __str__(self):
        output = []
        for f in fields(self):
            value = getattr(self, f.name)
            if value is not None:
                output.append(f"{f.name}={value}")
        return f"{self.__class__.__name__}({', '.join(output)})"

    def copy(self, **changes):
        return replace(self, **changes)


@dataclass
class PhaseRun(SystemRun):
    pass


@dataclass
class Proposal(PhaseRun):
    enabled: bool = True
    parent_id: object = None
    release_att_pool: bool = True
    atts_in_block: bool = True
    graffiti: str = None
    include_att_fn: Callable[[object, object], bool] = None

    def execute(self, fcr: FCRTest) -> object:
        if self.enabled:
            parent_root = fcr.get_block_root_or_head(self.parent_id)
            return fcr.add_and_apply_block(
                parent_root=parent_root,
                release_att_pool=self.release_att_pool,
                include_atts=self.atts_in_block,
                graffiti=self.graffiti,
                include_att_fn=self.include_att_fn,
            )
        else:
            return None


@dataclass
class Attesting(PhaseRun):
    block_id: object = None
    participation_rate: int = 100
    committee_slot_or_offset: object = 0

    def has_non_default_block(self) -> bool:
        return self.block_id != None

    def all_committee_slot_or_offsets(self):
        if isinstance(self.committee_slot_or_offset, list):
            yield from self.committee_slot_or_offset
        else:
            yield self.committee_slot_or_offset

    def execute(self, fcr: FCRTest) -> object:
        if self.participation_rate == 0:
            return []

        block_root = fcr.get_block_root_or_head(self.block_id)
        attestations = []
        for committee_slot_or_offset in self.all_committee_slot_or_offsets():
            attestations.extend(
                fcr.attest(
                    block_root=block_root,
                    slot=fcr.resolve_slot_by_offset(committee_slot_or_offset),
                    participation_rate=self.participation_rate,
                    pool_and_disseminate=True,
                )
            )

        # Instantly apply past slot attestations
        past_slot_attestations = [att for att in attestations if att.data.slot < fcr.current_slot()]
        fcr.apply_attestations(past_slot_attestations)

        return attestations


@dataclass
class Slashing(PhaseRun):
    percentage: int = None
    committee_slot_or_offset: int = None
    supporters_of_block: object = None

    def execute(self, fcr: FCRTest) -> object:
        if self.percentage == None or self.percentage == 0:
            return None

        if self.committee_slot_or_offset == None and self.supporters_of_block == None:
            return fcr.apply_attester_slashing(slashing_percentage=self.percentage)

        if self.committee_slot_or_offset != None:
            slot = fcr.resolve_slot_by_offset(self.committee_slot_or_offset)
            shuffling_source = fcr.store.block_states[fcr.head()]
            participants = fcr.sample_fraction_of_participants(
                shuffling_source, slot, self.percentage
            )
        else:
            supporters = fcr.get_supporters_of(self.supporters_of_block)
            count = len(supporters) * self.percentage // 100
            participants = supporters[:count]

        # Handle the case when there are no validators satisfying the above conditions
        if len(participants) > 0:
            return fcr.apply_attester_slashing(slashing_indices=participants)
        else:
            return None


@dataclass
class AdvanceSlot(PhaseRun):
    next_slot: bool = True
    with_fast_confirmation: bool = True

    def execute(self, fcr: FCRTest) -> object:
        # Next slot
        if self.next_slot:
            fcr.next_slot()

            # Run fast confirmation
            if self.with_fast_confirmation:
                fcr.run_fast_confirmation()

        return fcr.current_slot()


@dataclass
class MultiPhaseRun(SystemRun):
    proposal: Proposal = field(default_factory=lambda: Proposal())
    attesting: object = field(default_factory=lambda: Attesting())
    slashing: Slashing = field(default_factory=lambda: Slashing())
    advance_slot: AdvanceSlot = field(default_factory=lambda: AdvanceSlot())


@dataclass
class SlotRun(MultiPhaseRun):
    def all_attestings(self) -> list[Attesting]:
        if isinstance(self.attesting, list):
            yield from self.attesting
        else:
            yield self.attesting

    def execute(self, fcr: FCRTest) -> object:
        # Propose
        tip_root = self.proposal.execute(fcr)

        # Attest
        for attesting in self.all_attestings():
            if attesting.has_non_default_block():
                attesting.execute(fcr)
            else:
                attesting.copy(block_id=tip_root).execute(fcr)

        # Slash
        self.slashing.execute(fcr)

        # Next slot
        self.advance_slot.execute(fcr)

        return tip_root


@dataclass
class EmptySlotRun(SlotRun):
    proposal: Proposal = field(default_factory=lambda: Proposal(enabled=False))


@dataclass
class SlotSequence(MultiPhaseRun):
    number_of_slots: int = None
    end_slot: int = None
    branch_root_id: object = None

    def get_number_of_slots(self, current_slot):
        assert self.number_of_slots != None or self.end_slot != None
        if self.number_of_slots is not None:
            return self.number_of_slots
        else:
            assert self.end_slot > current_slot
            return self.end_slot - current_slot

    def execute(self, fcr: FCRTest) -> object:
        tip_root = fcr.get_block_root_or_head(self.branch_root_id)
        built_chain = []
        for _ in range(self.get_number_of_slots(fcr.current_slot())):
            tip_root = SlotRun(
                proposal=self.proposal.copy(parent_id=tip_root),
                attesting=self.attesting,
                slashing=self.slashing,
                advance_slot=self.advance_slot,
            ).execute(fcr)
            built_chain.append(tip_root)

        return built_chain
