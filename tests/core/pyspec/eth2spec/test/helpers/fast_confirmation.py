from dataclasses import dataclass
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
    add_attestations,
    add_attester_slashing,
    add_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
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
    test_steps.append(
        {
            "checks": {
                "previous_epoch_observed_justified_checkpoint": {
                    "epoch": int(store.previous_epoch_observed_justified_checkpoint.epoch),
                    "root": encode_hex(store.previous_epoch_observed_justified_checkpoint.root),
                },
                "current_epoch_observed_justified_checkpoint": {
                    "epoch": int(store.current_epoch_observed_justified_checkpoint.epoch),
                    "root": encode_hex(store.current_epoch_observed_justified_checkpoint.root),
                },
                "previous_slot_head": encode_hex(store.previous_slot_head),
                "current_slot_head": encode_hex(store.current_slot_head),
                "confirmed_root": encode_hex(store.confirmed_root),
            }
        }
    )


def on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps):
    spec.on_slot_start_after_past_attestations_applied(store)
    test_steps.append(
        {"slot_start_after_past_attestations_applied": int(spec.get_current_slot(store))}
    )
    output_fast_confirmation_checks(spec, store, test_steps)


@dataclass
class SystemRun:
    number_of_slots: int
    participation_rate: int = 100
    has_proposal: bool = True
    release_att_pool: bool = True
    atts_in_block: bool = True
    apply_atts: bool = True
    with_fast_confirmation: bool = True
    branch_root: object = None
    branch_root_slot_offset: int = None
    attesting_root: object = None
    attesting_root_slot_offset: int = None
    slashing_percentage: int = None
    slash_participants_in_slot_with_offset: int = None

    def get_block_root_by_slot(self, store, slot):
        block_roots_at_slot = [r for (r, b) in store.blocks.items() if b.slot == slot]
        assert len(block_roots_at_slot) > 0
        return block_roots_at_slot[0]

    def get_attesting_root(self, store, default_root, current_slot):
        if self.attesting_root_slot_offset != None:
            attesting_block_slot = int(current_slot) + self.attesting_root_slot_offset
            return self.get_block_root_by_slot(store, attesting_block_slot)
        elif self.attesting_root != None:
            return self.attesting_root
        else:
            return default_root

    def get_branch_root(self, store, default_root, current_slot):
        if self.branch_root != None:
            return self.branch_root
        elif self.branch_root_slot_offset != None:
            branch_root_slot = int(current_slot) + self.branch_root_slot_offset
            return self.get_block_root_by_slot(store, branch_root_slot)
        else:
            return default_root

    def has_slashing(self):
        return (
            self.slashing_percentage != None or self.slash_participants_in_slot_with_offset != None
        )

    def is_pure_slashing(self):
        return self.number_of_slots == 0 and self.has_slashing()


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

    def tick(self, slot):
        assert slot > self.current_slot() or slot == self.spec.GENESIS_SLOT
        current_time = slot * self.spec.config.SECONDS_PER_SLOT + self.store.genesis_time
        on_tick_and_append_step(self.spec, self.store, current_time, self.test_steps)

    def next_slot(self):
        self.tick(self.current_slot() + 1)
        # Discard outdated attestations from the pool
        if self.current_slot() % self.spec.SLOTS_PER_EPOCH == 0:
            self.attestation_pool = [
                a
                for a in self.attestation_pool
                if self.spec.compute_epoch_at_slot(a.data.slot) + 1 >= self.current_epoch()
            ]

    def max_attestations(self):
        if is_post_electra(self.spec):
            return self.spec.MAX_ATTESTATIONS_ELECTRA
        else:
            return self.spec.MAX_ATTESTATIONS

    def add_and_apply_block(
        self, parent_root=None, release_att_pool=True, graffiti: str = None, include_atts=True
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
        if include_atts:
            for attestation in self.attestation_pool[: self.max_attestations()]:
                block.body.attestations.append(attestation)

            # Release included attestations from the pool
            if release_att_pool:
                self.attestation_pool = self.attestation_pool[self.max_attestations() :]

        if graffiti is not None:
            block.body.graffiti = bytes(graffiti, "ascii").ljust(32, b"\x00")

        # Sign block and add it to the Store
        signed_block = state_transition_and_sign_block(self.spec, parent_state, block)
        for artefact in add_block(self.spec, self.store, signed_block, self.test_steps):
            self.blockchain_artefacts.append(artefact)

        return block.hash_tree_root()

    def attest(self, block_root=None, slot=None, participation_rate=100):
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

        # Prevent attesting if slot is incorrect
        # or too old such that committee shuffling would be incorrect
        assert slot >= att_state.slot
        assert self.spec.get_current_epoch(att_state) == self.spec.compute_epoch_at_slot(slot)

        # Advance state if needed
        transition_to(self.spec, att_state, slot)

        # Sample sleepy validators
        if participation_rate < 100:
            sleepy_participants = self.sample_sleepy_participants(
                att_state, slot, participation_rate
            )
        else:
            sleepy_participants = set()

        # Attest and add attestations to the pool
        attestations = get_valid_attestations_for_block_at_slot(
            self.spec,
            att_state,
            slot,
            block_root,
            participation_fn=(lambda slot, index, committee: committee - sleepy_participants),
        )
        self.attestation_pool.extend(attestations)

        return attestations

    def apply_attestations(self, attestations=None):
        if attestations is None:
            attestations = self.attestation_pool

        for artefact in add_attestations(self.spec, self.store, attestations, self.test_steps):
            self.blockchain_artefacts.append(artefact)

    def next_slot_and_apply_attestations(self):
        self.next_slot()
        self.apply_attestations()

    def run_fast_confirmation(self):
        on_slot_start_after_past_attestations_applied_and_append_step(
            self.spec, self.store, self.test_steps
        )

    def next_slot_with_block_and_apply_attestations(self, participation_rate=100):
        block_root = self.add_and_apply_block(parent_root=self.head())
        self.attest(
            block_root=self.head(), slot=self.current_slot(), participation_rate=participation_rate
        )
        self.next_slot()
        self.apply_attestations()
        return block_root

    def next_slot_with_block_and_fast_confirmation(self, participation_rate=100):
        block_root = self.next_slot_with_block_and_apply_attestations(participation_rate)
        self.run_fast_confirmation()
        return block_root

    def attest_and_next_slot_with_fast_confirmation(
        self, block_root=None, slot=None, participation_rate=100
    ):
        self.attest(block_root, slot, participation_rate)
        self.next_slot()
        self.apply_attestations()
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

    def sample_sleepy_participants(self, shuffling_source, slot, participation_rate):
        return self.sample_fraction_of_participants(
            shuffling_source, slot, 100 - participation_rate
        )

    def apply_attester_slashing(
        self, slashing_percentage: int = None, slashing_indices: list[int] = None, slot=None
    ):
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

    def execute_slashing(self, run: SystemRun):
        if run.slash_participants_in_slot_with_offset is not None:
            if run.slashing_percentage is None:
                slashing_percentage = 100
            else:
                slashing_percentage = run.slashing_percentage

            if slashing_percentage > 0:
                shuffling_source = self.store.block_states[self.head()]
                slot = int(self.current_slot()) + run.slash_participants_in_slot_with_offset
                participants = self.sample_fraction_of_participants(
                    shuffling_source, slot, slashing_percentage
                )
                self.apply_attester_slashing(slashing_indices=participants)
        elif run.slashing_percentage is not None and run.slashing_percentage > 0:
            self.apply_attester_slashing(slashing_percentage=run.slashing_percentage)

    def execute_run(self, run: SystemRun):
        debug_print(run)

        if run.is_pure_slashing():
            # Apply slashing and return
            self.execute_slashing(run)
            return

        tip_root = run.get_branch_root(self.store, self.head(), self.current_slot())
        for _ in range(run.number_of_slots):
            # Propose
            if run.has_proposal:
                tip_root = self.add_and_apply_block(
                    parent_root=tip_root,
                    release_att_pool=run.release_att_pool,
                    include_atts=run.atts_in_block,
                )

            # Attest
            attesting_root = run.get_attesting_root(
                self.store, default_root=tip_root, current_slot=self.current_slot()
            )
            attestations = self.attest(
                block_root=attesting_root,
                slot=self.current_slot(),
                participation_rate=run.participation_rate,
            )

            # Slash
            if run.has_slashing():
                self.execute_slashing(run)

            # Next slot
            self.next_slot()

            # Apply attestations to the fork choice
            if run.apply_atts:
                self.apply_attestations(attestations)

            # Run fast confirmation
            if run.with_fast_confirmation:
                self.run_fast_confirmation()

        if len(attestations) > 0:
            effective_participation = (
                len([bit for bit in attestations[0].aggregation_bits if bit])
                * 100.0
                / len(attestations[0].aggregation_bits)
            )
        else:
            effective_participation = 0
        debug_print(
            f"current_slot={self.current_slot()}, "
            f"head=({self.spec.get_block_slot(self.store, self.head())}, {self.head()}), "
            f"confirmed_block=({self.spec.get_block_slot(self.store, self.store.confirmed_root)}, {self.store.confirmed_root}), "
            f"effective_participation={effective_participation}, "
            f"UJ[head].epoch={self.store.unrealized_justifications[self.head()].epoch}"
        )


@dataclass
class CurrentEpochTestSpecification:
    head_uj_fresh: bool = (
        False  # <-> store.unrealized_justifications[head].epoch + 1 >= current_epoch
    )
    second_slot_call: bool = False  # <-> algorithm is called in the second slot of an epoch, this is the first slot when a block from the current epoch can possibly be confirmed
    first_block_in_epoch: bool = False  # <-> confirm the first block in the current epoch
    target_will_be_justified: bool = False  # <-> will_current_target_be_justified(store)
    is_one_confirmed: (
        bool  # <-> is_one_confirmed(store, get_current_balance_source(store), block_root)
    ) = False

    def verify_preconditions(self, spec, store):
        head = spec.get_head(store)
        current_epoch = spec.get_current_store_epoch(store)
        current_slot = spec.get_current_slot(store)
        confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)
        canonical_roots = spec.get_ancestor_roots(store, head, store.confirmed_root)

        assert confirmed_epoch + 1 >= current_epoch
        assert current_slot % spec.SLOTS_PER_EPOCH > 0
        assert len(canonical_roots) > 0

        assert self.second_slot_call == (current_slot % spec.SLOTS_PER_EPOCH == 1)
        assert self.first_block_in_epoch == (confirmed_epoch + 1 == current_epoch)
        assert self.head_uj_fresh == (
            store.unrealized_justifications[head].epoch + 1 >= current_epoch
        )
        assert self.target_will_be_justified == spec.will_current_target_be_justified(store)
        if self.is_one_confirmed:
            is_one_confirmed_list = [
                spec.is_one_confirmed(store, spec.get_current_balance_source(store), root)
                for root in canonical_roots
            ]
            debug_print(is_one_confirmed_list)
            assert all(is_one_confirmed_list)
        else:
            assert not spec.is_one_confirmed(
                store, spec.get_current_balance_source(store), spec.get_head(store)
            )

    def get_expected_confirmed_root(self, spec, store):
        confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)
        current_epoch = spec.get_current_store_epoch(store)

        if confirmed_epoch < current_epoch and not self.target_will_be_justified:
            return store.confirmed_root

        if self.head_uj_fresh and self.is_one_confirmed:
            # If any block is supposed to be confirmed
            # the head is always expected to be the most recent confirmed one
            return spec.get_head(store)
        else:
            return store.confirmed_root

    def first_block_at_mid_epoch(self):
        return self.first_block_in_epoch and not self.second_slot_call

    def one_confirmed_but_no_justification(self):
        return self.is_one_confirmed and not self.target_will_be_justified

    def first_block_in_second_slot(self):
        return self.first_block_in_epoch and self.second_slot_call


class CurrentEpochTestBuilder:
    def __init__(self, spec, state, seed, test_spec: CurrentEpochTestSpecification):
        self.spec = spec
        self.state = state
        self.seed = seed
        self.test_spec = test_spec

    def create_mid_runs_with_fresh_head_uj(self) -> list[SystemRun]:
        runs = []
        if self.test_spec.second_slot_call:
            # Nothing to do here
            pass
        elif (
            self.test_spec.first_block_in_epoch
            and self.test_spec.one_confirmed_but_no_justification()
        ):
            # Slash a fraction of validators each slot
            # and leave yet enough unslashed to make is_one_confirmed to pass
            # but will_current_target_be_justified to fail
            runs.append(
                SystemRun(
                    number_of_slots=1,
                    slashing_percentage=45,
                    slash_participants_in_slot_with_offset=0,
                )
            )
        elif self.test_spec.first_block_in_epoch:
            # Move on to the seconds slot in an epoch
            # with participation low enough to prevent confirming a block
            # but still enough to confirm it a slot after if needed
            runs.append(SystemRun(number_of_slots=1, participation_rate=85))
        else:
            # Move on to the seconds slot in an epoch
            # and confirm a block
            runs.append(SystemRun(number_of_slots=1))

            if self.test_spec.one_confirmed_but_no_justification():
                # Slash entire committee that has already confirmed a block,
                # this will result in will_current_target_be_justified to fail
                runs.append(
                    SystemRun(
                        number_of_slots=0,
                        slashing_percentage=100,
                        slash_participants_in_slot_with_offset=-1,
                    )
                )

        return runs

    def create_mid_runs_with_stale_head_uj(self) -> list[SystemRun]:
        # Run for an epoch with low onchain attestation inclusion
        # to prevent UJ update while keep fast confirming blocks
        slots_with_full_inclusion = self.spec.SLOTS_PER_EPOCH * 2 // 3
        slots_with_zero_inclusion = self.spec.SLOTS_PER_EPOCH - slots_with_full_inclusion
        runs = [
            SystemRun(number_of_slots=slots_with_full_inclusion, atts_in_block=True),
            SystemRun(number_of_slots=slots_with_zero_inclusion, atts_in_block=False),
        ]

        if self.test_spec.second_slot_call:
            # Nothing to do here
            pass
        elif (
            self.test_spec.first_block_in_epoch
            and self.test_spec.one_confirmed_but_no_justification()
        ):
            # Slash a fraction of validators each slot
            # and leave yet enough unslashed to make is_one_confirmed to pass
            # but will_current_target_be_justified to fail
            runs.append(
                SystemRun(
                    number_of_slots=1,
                    slashing_percentage=45,
                    slash_participants_in_slot_with_offset=0,
                    atts_in_block=False,
                )
            )
        elif self.test_spec.first_block_in_epoch:
            # Move on to the seconds slot in an epoch
            # without including atts in a block to prevent UJ update
            # and low participation enough to prevent is_one_confirmed from being True
            runs.append(SystemRun(number_of_slots=1, participation_rate=85, atts_in_block=False))
        else:
            # Create the following block tree:
            #   B
            #  /
            # A -- C, where:
            #
            # UJ[B].epoch == current_epoch - 1
            # UJ[C].epoch == current_epoch - 2
            # C == head
            #
            # Create A and attest to A
            runs.append(SystemRun(number_of_slots=1, atts_in_block=False))
            # Create B but attest to A
            # B includes attestations from previous epoch enough to update UJ
            runs.append(
                SystemRun(number_of_slots=1, atts_in_block=True, attesting_root_slot_offset=-1)
            )
            # Create C and attest to C, so C becomes the head, confirm A
            runs.append(SystemRun(number_of_slots=1, branch_root_slot_offset=-2))

            if self.test_spec.one_confirmed_but_no_justification():
                # Slash entire committee that has confirmed block A,
                # this will result in will_current_target_be_justified to fail
                runs.append(
                    SystemRun(
                        number_of_slots=0,
                        slashing_percentage=100,
                        slash_participants_in_slot_with_offset=-3,
                    )
                )

        return runs

    def create_mid_runs(self) -> list[SystemRun]:
        if self.test_spec.head_uj_fresh:
            return self.create_mid_runs_with_fresh_head_uj()
        else:
            return self.create_mid_runs_with_stale_head_uj()

    def get_final_run_participation_rate(self) -> int:
        if self.test_spec.is_one_confirmed:
            # Full participation
            return 100
        elif self.test_spec.target_will_be_justified:
            # Participation enough to justify a target
            # but not enough to fast confirm
            return 75
        else:
            # Participation enough neither to fast confirm
            # nor to justify a target
            return 0

    def create_final_run(self) -> SystemRun:
        if self.test_spec.first_block_at_mid_epoch():
            if self.test_spec.one_confirmed_but_no_justification():
                # Slash a fraction of validators each slot
                # and leave yet enough unslashed to make is_one_confirmed to pass
                # but will_current_target_be_justified to fail
                slashing_percentage = 45
            else:
                slashing_percentage = 0

            return SystemRun(
                number_of_slots=1,
                # Do not propose when the first block of the epoch
                # should be confirmed mid epoch
                has_proposal=False,
                # Prevent UJ update unless UJ must be fresh
                atts_in_block=self.test_spec.head_uj_fresh,
                participation_rate=self.get_final_run_participation_rate(),
                slashing_percentage=slashing_percentage,
                slash_participants_in_slot_with_offset=0,
                # Final run without fast confirmation as it will be triggered by the test execution
                with_fast_confirmation=False,
            )
        else:
            return SystemRun(
                number_of_slots=1,
                # Prevent UJ update unless UJ must be fresh
                atts_in_block=self.test_spec.head_uj_fresh,
                participation_rate=self.get_final_run_participation_rate(),
                # Final run without fast confirmation as it will be triggered by the test execution
                with_fast_confirmation=False,
            )

    def create_system_runs(self) -> list[SystemRun]:
        if self.test_spec.second_slot_call:
            assert self.test_spec.first_block_in_epoch, "Impossible in the second slot of an epoch"
        if self.test_spec.one_confirmed_but_no_justification():
            assert not self.test_spec.first_block_in_second_slot(), "The test is hard to build"

        # Initial run to the second epoch
        runs = [SystemRun(number_of_slots=self.spec.SLOTS_PER_EPOCH)]

        # Mid runs depending on the test spec
        runs.extend(self.create_mid_runs())

        # Final run
        runs.append(self.create_final_run())

        return runs

    def build(self):
        fcr_test = FCRTest(self.spec, self.seed)
        fcr_test.initialize(self.state)
        for run in self.create_system_runs():
            fcr_test.execute_run(run)

        # Check preconditions are correct
        self.test_spec.verify_preconditions(fcr_test.spec, fcr_test.store)

        return fcr_test
