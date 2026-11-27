"""Build the slot, participation, and finality history for inactivity fixtures."""

from functools import cache, cached_property
from itertools import batched

from eth_consensus_specs.test.helpers.attestations import get_valid_attestations_at_slot
from eth_consensus_specs.test.helpers.block import build_empty_block, sign_randao_reveal
from eth_consensus_specs.test.helpers.fulu.state import initialize_proposer_lookahead
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.gloas.state import initialize_ptc_window
from eth_consensus_specs.test.helpers.proposer_slashings import get_valid_proposer_slashing
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

FOCUS_INDEX = 0


class InactivityHistory:
    """Cache states at the last slot for callers to copy before choosing scores."""

    def __init__(self, spec):
        self.spec = spec
        self._starts = {}
        self._first_votes = {}
        self._finality_pairs = {}
        self._unvoted_epochs = {}

    def _advance(self, state, slot):
        if state.slot < slot:
            self.spec.process_slots(state, slot)

    def _block(self, state, slot, attested_slots=(), participants=None, *, slash=False):
        spec = self.spec
        self._advance(state, slot)
        with bls_enabled():
            block = build_empty_block(spec, state)
            block.body.eth1_data = state.eth1_data.copy()
            if slash:
                proof = get_valid_proposer_slashing(
                    spec,
                    state,
                    slashed_index=spec.ValidatorIndex(FOCUS_INDEX),
                    slot=slot - 1,
                    signed_1=True,
                    signed_2=True,
                )
                block.body.proposer_slashings.append(proof)

            def select(_slot, _committee_index, committee):
                return committee if participants is None else participants.intersection(committee)

            for attested_slot in attested_slots:
                votes = get_valid_attestations_at_slot(
                    state, spec, spec.Slot(attested_slot), participation_fn=select, payload_index=0
                )
                if votes:
                    block.body.attestations.append(spec.compute_on_chain_aggregate(votes))
            spec.process_block(state, block)

    def _seed_aged_checkpoint(self, state, epoch):
        """Carry the archived history into a checkpoint for the mainnet replay tail."""
        spec = self.spec
        # Commit the real part of the history, up to and including the slashing block.
        spec.process_slot(state)
        prefix_length = int(state.slot) + 1
        block_prefix = list(state.block_roots[:prefix_length])
        state_prefix = list(state.state_roots[:prefix_length])
        slashing_epoch = spec.get_current_epoch(state)
        state.slot = spec.compute_start_slot_at_epoch(epoch)

        def archived_root(kind, slot):
            return spec.Root(spec.sha256(kind + slot.to_bytes(8, "little")))

        # The checkpoint represents the older history by opaque roots. Its head
        # and ring agree so the following blocks can extend it normally.
        head_slot = int(state.slot) - 1
        head = spec.BeaconBlockHeader(
            slot=spec.Slot(head_slot),
            proposer_index=spec.get_beacon_proposer_indices(state, epoch - 1)[-1],
            parent_root=archived_root(b"block", head_slot - 1),
            state_root=archived_root(b"state", head_slot),
            body_root=archived_root(b"body", head_slot),
        )
        state.latest_block_header = head
        state.latest_execution_payload_bid.slot = head.slot
        state.latest_execution_payload_bid.parent_block_root = head.parent_root
        # The bid commits to the mix before the head's reveal was XORed in.
        archived_block = spec.BeaconBlock(slot=head.slot, proposer_index=head.proposer_index)
        with bls_enabled():
            sign_randao_reveal(spec, state, archived_block, head.proposer_index)
        head_mix = spec.get_randao_mix(state, spec.compute_epoch_at_slot(head.slot))
        state.latest_execution_payload_bid.prev_randao = spec.xor(
            head_mix, spec.sha256(archived_block.body.randao_reveal)
        )
        # The archived blocks are empty and never advance the execution hash.
        state.execution_payload_availability = spec.ExecutionPayloadAvailability()
        width = int(spec.SLOTS_PER_HISTORICAL_ROOT)
        for start in range(0, int(state.slot), width):
            slots = range(start, min(start + width, int(state.slot)))
            blocks = [archived_root(b"block", slot) for slot in slots]
            states = [archived_root(b"state", slot) for slot in slots]
            if start == 0:
                blocks[:prefix_length] = block_prefix
                states[:prefix_length] = state_prefix
            if head_slot in slots:
                blocks[-1] = spec.hash_tree_root(head)
            state.block_roots[: len(slots)] = blocks
            state.state_roots[: len(slots)] = states
            if len(slots) == width:
                state.historical_summaries.append(
                    spec.HistoricalSummary(
                        block_summary_root=spec.hash_tree_root(state.block_roots),
                        state_summary_root=spec.hash_tree_root(state.state_roots),
                    )
                )

        if epoch >= slashing_epoch + spec.EPOCHS_PER_SLASHINGS_VECTOR:
            state.slashings[slashing_epoch % spec.EPOCHS_PER_SLASHINGS_VECTOR] = spec.Gwei(0)
        # The checkpoint starts with a recent stalled finality history. Votes in
        # the replay tail can restore finality for the non-leaking cases.
        finalized_epoch = epoch - 6
        justified_epoch = finalized_epoch + 1
        state.finalized_checkpoint = spec.Checkpoint(
            epoch=finalized_epoch, root=spec.get_block_root(state, finalized_epoch)
        )
        justified = spec.Checkpoint(
            epoch=justified_epoch, root=spec.get_block_root(state, justified_epoch)
        )
        state.current_justified_checkpoint = justified
        state.previous_justified_checkpoint = justified.copy()
        # A committee is selected one period before it becomes current.
        period = spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
        period_start = epoch - epoch % period
        selection_state = state.copy()
        selection_state.slot = spec.compute_start_slot_at_epoch(period_start - period) - 1
        state.current_sync_committee = spec.get_next_sync_committee(selection_state)
        selection_state.slot = spec.compute_start_slot_at_epoch(period_start) - 1
        state.next_sync_committee = spec.get_next_sync_committee(selection_state)
        state.proposer_lookahead = initialize_proposer_lookahead(spec, state)
        state.ptc_window = initialize_ptc_window(spec, state)
        previous_slots = range(int(state.slot - spec.SLOTS_PER_EPOCH), int(state.slot))
        state.ptc_window[: spec.SLOTS_PER_EPOCH] = [
            spec.compute_ptc(state, spec.Slot(slot)) for slot in previous_slots
        ]
        voting_slots = int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD) * int(spec.SLOTS_PER_EPOCH)
        state.eth1_data_votes = spec.Eth1DataVotes(
            data=[state.eth1_data.copy() for _ in range(int(state.slot) % voting_slots)]
        )

    def _start(self, *, exited=False, aged=False, ineligible=False):
        key = (exited, aged, ineligible)
        if key not in self._starts:
            spec = self.spec
            balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
            balances = [balance] * 64
            if exited or aged:
                # Make the early exit fit into one epoch's churn on both presets.
                balances[FOCUS_INDEX] = (
                    spec.MIN_ACTIVATION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
                )
            if ineligible:
                balances.append(spec.MIN_DEPOSIT_AMOUNT)
            state = create_genesis_state(spec, balances, spec.MIN_ACTIVATION_BALANCE)
            if exited or aged:
                self._block(state, spec.Slot(2), slash=True)
                validator = state.validators[FOCUS_INDEX]
                if aged:
                    # Leave room for the finality history before the exact withdrawal boundary.
                    epoch = validator.withdrawable_epoch - 5
                    if spec.config.PRESET_BASE == "minimal":
                        self._advance(state, spec.compute_start_slot_at_epoch(epoch))
                    else:
                        self._seed_aged_checkpoint(state, epoch)
                else:
                    self._advance(state, spec.compute_start_slot_at_epoch(validator.exit_epoch + 1))
            self._starts[key] = state
        return self._starts[key].copy()

    @cached_property
    def genesis(self):
        return self._start()

    def _vote_current_epoch(self, state, *, flag_focus):
        spec = self.spec
        epoch = spec.get_current_epoch(state)
        start = int(spec.compute_start_slot_at_epoch(epoch))
        final_slot = start + int(spec.SLOTS_PER_EPOCH) - 1
        voters = set(spec.get_active_validator_indices(state, epoch))
        if not flag_focus:
            voters.discard(FOCUS_INDEX)
        # The final slot's vote is included after crossing the boundary.
        for slots in batched(range(start, final_slot), int(spec.MAX_ATTESTATIONS_ELECTRA)):
            self._block(state, spec.Slot(slots[-1] + 1), slots, voters)

    def _next_epoch_with_last_vote(self, state, *, flag_focus, slash=False):
        spec = self.spec
        epoch = spec.get_current_epoch(state)
        start = spec.compute_start_slot_at_epoch(epoch + 1)
        voters = set(spec.get_active_validator_indices(state, epoch))
        if not flag_focus:
            voters.discard(FOCUS_INDEX)
        self._block(state, start, (start - 1,), voters, slash=slash)

    def _finality_pair(
        self,
        *,
        exited=False,
        aged=False,
        ineligible=False,
        first_flag=True,
        second_flag=True,
        slash=False,
    ):
        key = (exited, aged, ineligible, first_flag, second_flag, slash)
        if key not in self._finality_pairs:
            spec = self.spec
            first_key = (exited, aged, ineligible, first_flag)
            if first_key not in self._first_votes:
                state = self._start(exited=exited, aged=aged, ineligible=ineligible)
                first = max(spec.get_current_epoch(state), spec.GENESIS_EPOCH + 2)
                self._advance(state, spec.compute_start_slot_at_epoch(first))
                self._vote_current_epoch(state, flag_focus=first_flag)
                self._first_votes[first_key] = state
            state = self._first_votes[first_key].copy()
            self._next_epoch_with_last_vote(state, flag_focus=first_flag, slash=slash)
            self._vote_current_epoch(state, flag_focus=second_flag)
            self._finality_pairs[key] = state
        return self._finality_pairs[key].copy()

    def _skip_to_epoch(self, key, state, epoch):
        spec = self.spec
        checkpoints = self._unvoted_epochs.setdefault(key, {spec.get_current_epoch(state): state})
        if epoch not in checkpoints:
            previous = max(earlier for earlier in checkpoints if earlier < epoch)
            state = checkpoints[previous].copy()
            self._advance(state, spec.compute_start_slot_at_epoch(epoch))
            checkpoints[epoch] = state
        return checkpoints[epoch].copy()

    def _vote_previous_epoch(self, state, voters):
        spec = self.spec
        if voters:
            start = state.slot
            previous_start = int(start - spec.SLOTS_PER_EPOCH)
            slots = range(previous_start, int(start))
            for i, group in enumerate(batched(slots, int(spec.MAX_ATTESTATIONS_ELECTRA))):
                self._block(state, start + i, group, voters)

    def _at_last_slot(self, state):
        spec = self.spec
        self._advance(
            state, spec.compute_start_slot_at_epoch(spec.get_current_epoch(state) + 1) - 1
        )
        return state

    @cached_property
    def outer(self):
        return cache(self._outer)

    def _outer(
        self,
        *,
        after_genesis,
        leaking=False,
        slashed=False,
        matured=False,
        ineligible=False,
        branch="ALL_INCREMENT",
    ):
        spec = self.spec
        if not after_genesis:
            return self._at_last_slot(self.genesis.copy())
        extra_ineligible = ineligible and not matured
        if slashed:
            state = (
                self._start(aged=True, ineligible=extra_ineligible)
                if leaking
                else self._finality_pair(aged=True, ineligible=extra_ineligible)
            )
            epoch = state.validators[FOCUS_INDEX].withdrawable_epoch - int(not matured)
        else:
            state = self._start(ineligible=ineligible)
            epoch = spec.get_current_epoch(state) + (
                spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2 if leaking else 3
            )
        state = self._skip_to_epoch(
            ("outer", slashed, extra_ineligible, slashed and not leaking), state, epoch
        )
        voters = set()
        if branch == "ALL_DECREMENT":
            voters.update(spec.get_active_validator_indices(state, epoch - 1))
        elif branch == "MIXED":
            voters.add(spec.ValidatorIndex(FOCUS_INDEX + 1))
        self._vote_previous_epoch(state, voters)
        return self._at_last_slot(state)

    @cached_property
    def loop(self):
        return cache(self._loop)

    def _loop(self, *, delay, active, flagged, slashed):
        spec = self.spec
        late_slash = active and slashed
        if delay == 0:
            state = self._finality_pair(exited=not active, first_flag=flagged, slash=late_slash)
        elif delay == 1:
            state = self._finality_pair(exited=not active, second_flag=flagged)
            self._next_epoch_with_last_vote(state, flag_focus=flagged, slash=late_slash)
        else:
            state = self._finality_pair(exited=not active)
            epoch = spec.get_current_epoch(state) + delay
            state = self._skip_to_epoch(("loop", active), state, epoch)
            voters = {spec.ValidatorIndex(FOCUS_INDEX)} if flagged else set()
            self._vote_previous_epoch(state, voters)
            if late_slash:
                self._block(state, state.slot + 1, slash=True)
        return self._at_last_slot(state)
