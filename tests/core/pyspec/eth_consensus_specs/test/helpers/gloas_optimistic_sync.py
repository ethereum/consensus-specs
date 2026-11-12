"""Test harness for ``specs/gloas/optimistic-sync.md``."""

from dataclasses import dataclass
from typing import Any

from eth_utils import encode_hex

from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.execution_payload import (
    build_empty_execution_payload,
    compute_el_block_hash_with_new_fields,
    compute_requests_hash,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    get_block_file_name,
    get_execution_payload_envelope_file_name,
    get_genesis_forkchoice_store_and_block,
    run_on_block,
)
from eth_consensus_specs.test.helpers.optimistic_sync import (
    PayloadStatusV1,
    PayloadStatusV1Status,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

VALID = "VALID"
NOT_VALIDATED = "NOT_VALIDATED"
INVALIDATED = "INVALIDATED"


def syncing():
    return PayloadStatusV1(status=PayloadStatusV1Status.SYNCING)


def accepted():
    return PayloadStatusV1(status=PayloadStatusV1Status.ACCEPTED)


def valid(block_hash):
    return PayloadStatusV1(status=PayloadStatusV1Status.VALID, latest_valid_hash=block_hash)


def invalid(latest_valid_hash):
    return PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=latest_valid_hash,
        validation_error="invalid",
    )


@dataclass
class GloasBlock:
    """A signed block, its post-state and the envelope that reveals its payload."""

    signed_block: Any
    state: Any
    envelope: Any

    @property
    def root(self):
        return self.signed_block.message.hash_tree_root()

    @property
    def slot(self):
        return self.signed_block.message.slot

    @property
    def block_hash(self):
        return self.signed_block.message.body.signed_execution_payload_bid.message.block_hash

    @property
    def parent_block_hash(self):
        return self.signed_block.message.body.signed_execution_payload_bid.message.parent_block_hash


class GloasOptimisticRig:
    """
    Fork choice with ``specs/gloas/optimistic-sync.md`` on top: the ``full`` node of every block
    that committed to an ``INVALIDATED`` payload is removed with all its descendants, and removed
    nodes are neither viable for head nor counted in weights.
    """

    def __init__(self, spec, state, test_steps, slot):
        self.spec = spec
        self.test_steps = test_steps
        self.store, self.anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
        anchor_root = self.anchor_block.hash_tree_root()
        self.anchor_state = state.copy()
        self.opt_store = spec.OptimisticStore(
            optimistic_payloads=set(),
            head_block_root=anchor_root,
            blocks={anchor_root: self.anchor_block.copy()},
            block_states={anchor_root: state.copy()},
        )
        # The anchor's payload is assumed VALID (see "Checkpoint Sync" in optimistic-sync.md).
        self.anchor_block_hash = state.latest_block_hash
        self.payload_parent = {self.anchor_block_hash: None}
        self.invalidated_payloads = set()
        # The latest `on_payload_info` response per block hash, for newPayload and fcU alike.
        self.engine_responses = {}
        # The head node the last `engine_forkchoiceUpdated` was sent for.
        self.forkchoice_head = None
        # Payloads whose envelopes fork choice imported, in import order.
        self.imported_payloads = []
        self.tick(slot)

    # Block and envelope construction

    def build(self, parent, parent_full=False, slot=None, salt=None, graffiti=None):
        """
        Build a block on ``parent`` (a ``GloasBlock`` or ``None`` for the anchor) and the envelope
        that reveals its payload, with an execution block hash computed over the payload.

        ``parent_full`` picks the parent node the block extends. ``salt`` goes into
        ``extra_data`` to give sibling payloads distinct block hashes.
        """
        spec = self.spec
        state = (self.anchor_state if parent is None else parent.state).copy()
        if slot is None:
            slot = state.slot + 1

        block = build_empty_block(spec, state, slot)
        if graffiti is not None:
            block.body.graffiti = spec.Bytes32(graffiti.ljust(32, b"\x00"))
        bid = block.body.signed_execution_payload_bid.message
        if parent_full:
            bid.parent_block_hash = parent.block_hash
        # A placeholder hash, replaced once the payload is known.
        bid.block_hash = spec.Hash32(b"\x01" + b"\x00" * 31)

        # The payload commits to fields of the post-state (withdrawals), so run the transition
        # once to learn them.
        post_state = state.copy()
        state_transition_and_sign_block(spec, post_state, block.copy())
        payload = build_empty_execution_payload(spec, post_state)
        payload.parent_hash = post_state.latest_block_hash
        payload.withdrawals = post_state.payload_expected_withdrawals
        if salt is not None:
            payload.extra_data = spec.ExtraData(data=list(salt))
        requests = spec.ExecutionRequests()
        payload.block_hash = compute_el_block_hash_with_new_fields(
            spec,
            payload,
            block.parent_root,
            compute_requests_hash(spec.get_execution_requests_list(requests)),
        )
        bid.block_hash = payload.block_hash

        signed_block = state_transition_and_sign_block(spec, state, block)
        envelope = spec.ExecutionPayloadEnvelope(
            payload=payload,
            execution_requests=requests,
            builder_index=bid.builder_index,
            beacon_block_root=signed_block.message.hash_tree_root(),
            parent_beacon_block_root=block.parent_root,
        )
        signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
        return GloasBlock(signed_block, state, signed_envelope)

    # Fork choice model

    def bid(self, root):
        return self.store.blocks[root].body.signed_execution_payload_bid.message

    def full_node(self, root):
        return self.spec.ForkChoiceNode(root=root, payload_status=self.spec.PAYLOAD_STATUS_FULL)

    def empty_node(self, root):
        return self.spec.ForkChoiceNode(root=root, payload_status=self.spec.PAYLOAD_STATUS_EMPTY)

    def is_removed(self, node):
        return any(
            self.spec.is_ancestor(self.store, node, self.full_node(root))
            for root in self.store.payloads
            if self.bid(root).block_hash in self.invalidated_payloads
        )

    def attestation_score(self, node, state):
        """``get_attestation_score`` without the votes for removed nodes."""
        spec = self.spec
        store = self.store
        total = 0
        for index in spec.get_active_validator_indices(state, spec.get_current_epoch(state)):
            if (
                state.validators[index].slashed
                or index not in store.latest_messages
                or index in store.equivocating_indices
            ):
                continue
            supported = spec.get_supported_node(store, store.latest_messages[index])
            if not self.is_removed(supported) and spec.is_ancestor(store, supported, node):
                total += state.validators[index].effective_balance
        return spec.Gwei(total)

    def weight(self, node):
        """``get_weight`` with ``attestation_score`` in place of ``get_attestation_score``."""
        spec = self.spec
        store = self.store
        if spec.is_previous_slot_payload_decision(store, node):
            return spec.Gwei(0)
        score = self.attestation_score(node, store.checkpoint_states[store.justified_checkpoint])
        boost = spec.ForkChoiceNode(
            root=store.proposer_boost_root, payload_status=spec.PAYLOAD_STATUS_PENDING
        )
        if spec.should_apply_proposer_boost(store) and spec.is_ancestor(store, boost, node):
            score += spec.get_proposer_score(store)
        return score

    def head(self):
        """``get_head`` over the node tree without removed nodes."""
        spec = self.spec
        store = self.store
        nodes = [node for node in spec.get_filtered_node_tree(store) if not self.is_removed(node)]
        head = spec.ForkChoiceNode(
            root=store.justified_checkpoint.root, payload_status=spec.PAYLOAD_STATUS_PENDING
        )
        while children := [c for c in spec.get_node_children(store, head) if c in nodes]:
            head = max(
                children,
                key=lambda child: (
                    self.weight(child),
                    child.root,
                    spec.get_payload_status_tiebreaker(store, child),
                ),
            )
        return head

    def payload_status(self, block_hash):
        if block_hash in self.invalidated_payloads:
            return INVALIDATED
        if block_hash in self.opt_store.optimistic_payloads:
            return NOT_VALIDATED
        return VALID

    def payload_ancestors(self, block_hash):
        """``block_hash`` and every known payload it builds on, child first."""
        chain = []
        while block_hash in self.payload_parent:
            chain.append(block_hash)
            block_hash = self.payload_parent[block_hash]
        return chain

    def mark_valid(self, block_hash):
        """``NOT_VALIDATED`` -> ``VALID`` for ``block_hash`` and all its ancestor payloads."""
        for ancestor in self.payload_ancestors(block_hash):
            assert ancestor not in self.invalidated_payloads, (
                "an EL cannot validate an invalid chain"
            )
            self.opt_store.optimistic_payloads.discard(ancestor)

    def mark_invalid(self, block_hash):
        """``NOT_VALIDATED`` -> ``INVALIDATED`` for ``block_hash`` and all its descendants."""
        for descendant in self.payload_parent:
            if block_hash not in self.payload_ancestors(descendant):
                continue
            assert self.payload_status(descendant) != VALID, (
                "an EL cannot invalidate a VALID payload"
            )
            self.opt_store.optimistic_payloads.discard(descendant)
            self.invalidated_payloads.add(descendant)

    def invalid_payload(self, chain, latest_valid_hash):
        """
        ``invalidPayload`` for an ``INVALID`` verdict on ``chain[0]``, with ``chain`` that payload
        and its ancestors, child first.
        """
        # The spec's all-zero case names "the first payload of that chain", which is open when the
        # chain starts at a checkpoint sync anchor.
        if latest_valid_hash is None:
            return chain[0]
        assert latest_valid_hash != self.spec.Hash32(), "an all-zero latest valid hash"
        if latest_valid_hash not in chain[1:]:
            return chain[0]
        return chain[chain.index(latest_valid_hash) - 1]

    def apply_invalid(self, block_hash, parent_hash, latest_valid_hash):
        """Apply an ``INVALID`` verdict on the rejected payload ``block_hash``."""
        invalid_payload = self.invalid_payload(
            [block_hash] + self.payload_ancestors(parent_hash), latest_valid_hash
        )
        # An equivocating block may have imported the same payload.
        if block_hash in self.payload_parent:
            self.mark_invalid(block_hash)
        else:
            self.invalidated_payloads.add(block_hash)
        if invalid_payload != block_hash:
            self.mark_invalid(invalid_payload)

    def notify_forkchoice_updated(self):
        """
        Send ``engine_forkchoiceUpdated`` whenever the head node changes, even if its
        ``headBlockHash`` does not, and apply the response. Repeat until the head settles.
        """
        while (head := self.head()) != self.forkchoice_head:
            self.forkchoice_head = head
            bid = self.bid(head.root)
            if head.payload_status == self.spec.PAYLOAD_STATUS_FULL:
                block_hash = bid.block_hash
            else:
                block_hash = bid.parent_block_hash
            response = self.engine_responses.get(block_hash)
            if response is None:
                continue
            if response.status == PayloadStatusV1Status.VALID:
                self.mark_valid(block_hash)
            elif response.status == PayloadStatusV1Status.INVALID:
                self.mark_invalid(
                    self.invalid_payload(
                        self.payload_ancestors(block_hash), response.latest_valid_hash
                    )
                )
        return head

    # Steps

    def set_payload_info(self, block_hash, payload_status):
        """Set the execution engine's response for ``block_hash`` without delivering anything."""
        self.engine_responses[block_hash] = payload_status
        self.test_steps.append(
            {
                "block_hash": encode_hex(block_hash),
                "payload_status": payload_status.formatted_output,
            }
        )

    def tick(self, slot):
        # Not `on_tick_and_append_step`: `get_head` still sees removed nodes.
        spec = self.spec
        time_ms = spec.compute_time_at_slot_ms(self.store.genesis_time_ms, slot)
        assert time_ms >= self.store.time_ms
        spec.on_tick(self.store, time_ms)
        self.test_steps.append({"tick": int(spec.milliseconds_to_seconds(time_ms))})
        self.output_checks()

    def add_block(self, block, expect_valid=None):
        """Deliver ``block``. A block that extends a removed node is rejected."""
        spec = self.spec
        signed_block = block.signed_block
        message = signed_block.message
        yield get_block_file_name(signed_block), signed_block
        parent_node = spec.ForkChoiceNode(
            root=message.parent_root,
            payload_status=spec.get_parent_payload_status(self.store, message),
        )
        is_valid = not self.is_removed(parent_node)
        assert expect_valid in (None, is_valid), "unexpected block validity"
        if is_valid:
            run_on_block(spec, self.store, signed_block, valid=True)
            self.opt_store.blocks[block.root] = message.copy()
            self.opt_store.block_states[block.root] = self.store.block_states[block.root].copy()
        self.test_steps.append({"block": get_block_file_name(signed_block), "valid": is_valid})
        self.output_checks()

    def add_envelope(self, block, payload_status):
        """
        Deliver ``block``'s envelope, with ``payload_status`` the execution engine's response
        to ``engine_newPayload``.
        """
        spec = self.spec
        envelope = block.envelope
        payload = envelope.message.payload
        block_hash = payload.block_hash
        file_name = get_execution_payload_envelope_file_name(envelope)
        yield file_name, envelope
        self.set_payload_info(block_hash, payload_status)

        # The envelope passes every check but the execution engine's.
        spec.on_execution_payload_envelope(self.store, envelope)
        del self.store.payloads[envelope.message.beacon_block_root]

        status = payload_status.status
        if payload.parent_hash in self.invalidated_payloads:
            is_accepted = False
        elif status == PayloadStatusV1Status.INVALID:
            is_accepted = False
            self.apply_invalid(block_hash, payload.parent_hash, payload_status.latest_valid_hash)
        else:
            is_accepted = True
            spec.on_execution_payload_envelope(self.store, envelope)
            self.payload_parent[block_hash] = payload.parent_hash
            if block_hash not in self.imported_payloads:
                self.imported_payloads.append(block_hash)
            if status == PayloadStatusV1Status.VALID:
                self.mark_valid(block_hash)
            else:
                self.opt_store.optimistic_payloads.add(block_hash)
        self.test_steps.append({"execution_payload": file_name, "valid": is_accepted})
        self.output_checks()
        return is_accepted

    def state_at(self, block, slot):
        state = block.state.copy()
        if state.slot < slot:
            self.spec.process_slots(state, slot)
        return state

    def attest(self, block, slot, index, participants, payload_index):
        attestation = get_valid_attestation(
            self.spec,
            self.state_at(block, slot),
            slot=slot,
            index=index,
            payload_index=payload_index,
            beacon_block_root=block.root,
            filter_participant_set=lambda committee: set(participants) & set(committee),
            signed=True,
        )
        yield from add_attestation(self.spec, self.store, attestation, self.test_steps)

    def add_attestation(self, block, slot, participants, payload_present):
        """
        Deliver an attestation at ``slot`` for ``block`` from the ``participants`` of the slot's
        first committee. ``payload_present`` picks the ``full`` or ``empty`` node of a block from
        an earlier slot.
        """
        payload_index = (1 if payload_present else 0) if block.slot < slot else None
        yield from self.attest(block, slot, 0, participants, payload_index)
        self.output_checks()

    def add_votes(self, block, epoch, validators, payload_present):
        """
        Deliver attestations for ``block`` from ``validators``, each at its assigned slot in
        ``epoch``. Every slot must be later than ``block``'s.
        """
        spec = self.spec
        start_slot = spec.compute_start_slot_at_epoch(epoch)
        for slot in range(start_slot, start_slot + spec.SLOTS_PER_EPOCH):
            assert slot > block.slot
            state = self.state_at(block, slot)
            for index in range(spec.get_committee_count_per_slot(state, epoch)):
                participants = set(validators) & set(spec.get_beacon_committee(state, slot, index))
                if len(participants) > 0:
                    yield from self.attest(
                        block, slot, index, participants, 1 if payload_present else 0
                    )
        self.output_checks()

    def committee(self, block, slot):
        """The first committee at ``slot`` on ``block``'s chain."""
        return sorted(self.spec.get_beacon_committee(self.state_at(block, slot), slot, 0))

    def output_checks(self):
        head = self.notify_forkchoice_updated()
        self.opt_store.head_block_root = head.root
        self.test_steps.append(
            {
                "checks": {
                    "head": {
                        "slot": int(self.store.blocks[head.root].slot),
                        "root": encode_hex(head.root),
                        "payload_status": int(head.payload_status),
                    },
                    "execution_payload_statuses": [
                        {
                            "block_hash": encode_hex(block_hash),
                            "status": self.payload_status(block_hash),
                        }
                        for block_hash in self.imported_payloads
                    ],
                }
            }
        )

    def assert_head(self, root, payload_status):
        assert self.head() == self.spec.ForkChoiceNode(root=root, payload_status=payload_status)

    def is_optimistic(self, node):
        return self.spec.is_optimistic(self.opt_store, node)
