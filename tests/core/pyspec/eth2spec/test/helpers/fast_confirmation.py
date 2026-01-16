from random import Random

from eth_utils import encode_hex

from eth2spec.test.helpers.attestations import (
    get_valid_attestations_for_block_at_slot,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
)
from eth2spec.test.helpers.fork_choice import (
    add_attestations,
    add_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)


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


class FCRTest:
    def __init__(self, spec):
        self.spec = spec

    def initialize(self, anchor_state, seed):
        # Initialization
        test_steps = []
        store, anchor_block = get_genesis_forkchoice_store_and_block(self.spec, anchor_state)

        self.store = store
        self.test_steps = test_steps
        self.attestation_pool = []
        self.blockchain_artefacts = []
        self.rng = Random(seed)

        # Tick
        self.tick(self.spec.GENESIS_SLOT)

        self.blockchain_artefacts.append(("anchor_state", anchor_state))
        self.blockchain_artefacts.append(("anchor_block", anchor_block))

        return store

    def get_test_artefacts(self):
        return self.blockchain_artefacts + [("steps", self.test_steps)]

    def current_slot(self):
        return self.spec.get_current_slot(self.store)

    def head(self):
        return self.spec.get_head(self.store)

    def tick(self, slot):
        assert slot > self.current_slot() or slot == self.spec.GENESIS_SLOT
        current_time = slot * self.spec.config.SECONDS_PER_SLOT + self.store.genesis_time
        on_tick_and_append_step(self.spec, self.store, current_time, self.test_steps)

    def next_slot(self):
        self.tick(self.current_slot() + 1)

    def add_and_apply_block(self, parent_root=None):
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
        for attestation in self.attestation_pool:
            block.body.attestations.append(attestation)

        # Release included attestations from the pool
        self.attestation_pool = []

        # Sign block and add it to the Store
        signed_block = state_transition_and_sign_block(self.spec, parent_state, block)
        for artefact in add_block(self.spec, self.store, signed_block, self.test_steps):
            self.blockchain_artefacts.append(artefact)

        return block.hash_tree_root()

    def attest(self, block_root=None, slot=None, participation_rate=100):
        assert 0 <= participation_rate <= 100

        # Do not attest if participation is zero
        if participation_rate == 0:
            return

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

    def next_slot_with_block_and_fast_confirmation(self, participation_rate=100):
        block_root = self.add_and_apply_block(parent_root=self.head())
        self.attest(
            block_root=self.head(), slot=self.current_slot(), participation_rate=participation_rate
        )
        self.next_slot()
        self.apply_attestations()
        self.run_fast_confirmation()
        return block_root

    def empty_slot_with_fast_confirmation(self, participation_rate=100):
        self.attest(
            block_root=self.head(), slot=self.current_slot(), participation_rate=participation_rate
        )
        self.next_slot()
        self.apply_attestations()
        self.run_fast_confirmation()

    def run_slots_with_blocks_and_fast_confirmation(self, slot_number, participation_rate=100):
        for _ in range(slot_number):
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

    def sample_sleepy_participants(self, shuffling_source, slot, participation_rate):
        slot_committee = self.get_slot_committee(shuffling_source, slot)
        sleepy_participants_count = len(slot_committee) * (100 - participation_rate) // 100
        self.rng.shuffle(slot_committee)
        return set(slot_committee[:sleepy_participants_count])
