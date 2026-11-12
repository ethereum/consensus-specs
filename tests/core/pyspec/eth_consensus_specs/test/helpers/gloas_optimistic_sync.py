"""
Gloas optimistic sync test harness.

A Gloas block commits to the payload it builds on (``bid.parent_block_hash``) and its own payload
arrives later in an envelope. The execution engine judges payloads, so optimistic status is
tracked per payload, as in ``specs/gloas/optimistic-sync.md``:

- ``opt_store.optimistic_payloads`` holds the payloads that only received ``NOT_VALIDATED``.
- ``invalidated_payloads`` holds the payloads that transitioned to ``INVALIDATED``.

Removing an ``INVALIDATED`` payload from fork choice removes the ``full`` node of every block that
committed to it and every node descending from that ``full`` node. The ``empty`` node of that
block stays. Removed nodes are neither viable for head nor counted in weights.

Every execution engine response is delivered through an ``on_payload_info`` step before the
call it answers. An ``INVALID`` response rejects the envelope, so its step is ``valid: false``.
"""

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


class GloasBlock:
    """A signed block, its post-state and the envelope that reveals its payload."""

    def __init__(self, signed_block, state, envelope):
        self.signed_block = signed_block
        self.state = state
        self.envelope = envelope

    @property
    def root(self):
        return self.signed_block.message.hash_tree_root()

    @property
    def slot(self):
        return self.signed_block.message.slot

    @property
    def bid(self):
        return self.signed_block.message.body.signed_execution_payload_bid.message

    @property
    def block_hash(self):
        return self.bid.block_hash

    @property
    def parent_block_hash(self):
        return self.bid.parent_block_hash


class GloasOptimisticRig:
    def __init__(self, spec, state, test_steps):
        self.spec = spec
        self.test_steps = test_steps
        self.store, self.anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
        self.anchor_root = self.anchor_block.hash_tree_root()
        self.anchor_state = state.copy()
        self.opt_store = spec.OptimisticStore(
            optimistic_payloads=set(),
            head_block_root=self.anchor_root,
            blocks={self.anchor_root: self.anchor_block.copy()},
            block_states={self.anchor_root: state.copy()},
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

    # Block and envelope construction

    def build(self, parent, parent_full=False, slot=None, salt=None, graffiti=None):
        """
        Build a block on ``parent`` (a ``GloasBlock`` or ``None`` for the anchor) and the envelope
        that reveals its payload, with an execution block hash computed over the payload.

        ``parent_full`` picks the parent node the block extends. ``salt`` goes into
        ``extra_data`` to give sibling payloads distinct block hashes.
        """
        spec = self.spec
        if parent is None:
            state = self.anchor_state.copy()
            parent_slot = self.anchor_state.slot
        else:
            state = parent.state.copy()
            parent_slot = parent.slot
        if slot is None:
            slot = parent_slot + 1

        block = build_empty_block(spec, state, slot)
        if graffiti is not None:
            block.body.graffiti = spec.Bytes32(graffiti.ljust(32, b"\x00"))
        bid = block.body.signed_execution_payload_bid.message
        if parent_full:
            assert parent is not None
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

    def full_node(self, root):
        return self.spec.ForkChoiceNode(root=root, payload_status=self.spec.PAYLOAD_STATUS_FULL)

    def empty_node(self, root):
        return self.spec.ForkChoiceNode(root=root, payload_status=self.spec.PAYLOAD_STATUS_EMPTY)

    def removed_full_nodes(self):
        return [
            self.full_node(root)
            for root in self.store.payloads
            if self.store.blocks[root].body.signed_execution_payload_bid.message.block_hash
            in self.invalidated_payloads
        ]

    def is_removed(self, node):
        return any(
            self.spec.is_ancestor(self.store, node, removed)
            for removed in self.removed_full_nodes()
        )

    def attestation_score(self, node, state):
        """``get_attestation_score`` without the votes for removed nodes."""
        spec = self.spec
        store = self.store
        total = 0
        for index in spec.get_active_validator_indices(state, spec.get_current_epoch(state)):
            if state.validators[index].slashed:
                continue
            if index not in store.latest_messages or index in store.equivocating_indices:
                continue
            supported = spec.get_supported_node(store, store.latest_messages[index])
            if self.is_removed(supported):
                continue
            if spec.is_ancestor(store, supported, node):
                total += state.validators[index].effective_balance
        return spec.Gwei(total)

    def weight(self, node):
        """``get_weight`` with ``attestation_score`` in place of ``get_attestation_score``."""
        spec = self.spec
        store = self.store
        if spec.is_previous_slot_payload_decision(store, node):
            return spec.Gwei(0)
        score = self.attestation_score(node, store.checkpoint_states[store.justified_checkpoint])
        if not spec.should_apply_proposer_boost(store):
            return score
        if spec.is_ancestor(
            store,
            spec.ForkChoiceNode(
                root=store.proposer_boost_root, payload_status=spec.PAYLOAD_STATUS_PENDING
            ),
            node,
        ):
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
        while True:
            children = [child for child in spec.get_node_children(store, head) if child in nodes]
            if len(children) == 0:
                return head
            head = max(
                children,
                key=lambda child: (
                    self.weight(child),
                    child.root,
                    spec.get_payload_status_tiebreaker(store, child),
                ),
            )

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

    def payload_descendants(self, block_hash):
        descendants = {block_hash}
        changed = True
        while changed:
            changed = False
            for child, parent in self.payload_parent.items():
                if parent in descendants and child not in descendants:
                    descendants.add(child)
                    changed = True
        return descendants

    def mark_valid(self, block_hash):
        """``NOT_VALIDATED`` -> ``VALID`` for ``block_hash`` and all its ancestor payloads."""
        for ancestor in self.payload_ancestors(block_hash):
            assert ancestor not in self.invalidated_payloads, (
                "an EL cannot validate an invalid chain"
            )
            self.opt_store.optimistic_payloads.discard(ancestor)

    def mark_invalid(self, block_hash):
        """``NOT_VALIDATED`` -> ``INVALIDATED`` for ``block_hash`` and all its descendants."""
        for descendant in self.payload_descendants(block_hash):
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

    def head_block_hash(self, head):
        """The execution block hash a ``forkchoiceUpdated`` for ``head`` names."""
        bid = self.store.blocks[head.root].body.signed_execution_payload_bid.message
        if head.payload_status == self.spec.PAYLOAD_STATUS_FULL:
            return bid.block_hash
        return bid.parent_block_hash

    def notify_forkchoice_updated(self):
        """
        Send ``engine_forkchoiceUpdated`` whenever the head node changes, even if its
        ``headBlockHash`` does not, and apply the response. Repeat until the head settles.
        """
        while True:
            head = self.head()
            if head == self.forkchoice_head:
                return head
            self.forkchoice_head = head
            block_hash = self.head_block_hash(head)
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
        """
        Deliver ``block``. A block that extends a removed node is rejected.
        """
        spec = self.spec
        signed_block = block.signed_block
        yield get_block_file_name(signed_block), signed_block
        parent = self.store.blocks.get(signed_block.message.parent_root)
        extends_removed = False
        if parent is not None:
            parent_node = spec.ForkChoiceNode(
                root=signed_block.message.parent_root,
                payload_status=spec.get_parent_payload_status(self.store, signed_block.message),
            )
            extends_removed = self.is_removed(parent_node)
        if extends_removed:
            assert expect_valid is not True, "expected a valid block"
            self.test_steps.append({"block": get_block_file_name(signed_block), "valid": False})
            self.output_checks()
            return
        assert expect_valid is not False, "expected an invalid block"
        run_on_block(spec, self.store, signed_block, valid=True)
        root = signed_block.message.hash_tree_root()
        self.opt_store.blocks[root] = signed_block.message.copy()
        self.opt_store.block_states[root] = self.store.block_states[root].copy()
        self.test_steps.append({"block": get_block_file_name(signed_block), "valid": True})
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
        parent_hash = payload.parent_hash
        file_name = get_execution_payload_envelope_file_name(envelope)
        yield file_name, envelope
        self.set_payload_info(block_hash, payload_status)

        # The envelope passes every check but the execution engine's.
        spec.on_execution_payload_envelope(self.store, envelope)
        del self.store.payloads[envelope.message.beacon_block_root]

        status = payload_status.status
        if parent_hash in self.invalidated_payloads:
            accepted = False
        elif status in (
            PayloadStatusV1Status.VALID,
            PayloadStatusV1Status.SYNCING,
            PayloadStatusV1Status.ACCEPTED,
        ):
            accepted = True
        elif status == PayloadStatusV1Status.INVALID:
            accepted = False
            self.apply_invalid(block_hash, parent_hash, payload_status.latest_valid_hash)
        else:
            raise AssertionError(f"unknown status {status}")

        if accepted:
            spec.on_execution_payload_envelope(self.store, envelope)
            self.payload_parent[block_hash] = parent_hash
            if block_hash not in self.imported_payloads:
                self.imported_payloads.append(block_hash)
            if status == PayloadStatusV1Status.VALID:
                self.mark_valid(block_hash)
            else:
                self.opt_store.optimistic_payloads.add(block_hash)
        self.test_steps.append({"execution_payload": file_name, "valid": accepted})
        self.output_checks()
        return accepted

    def add_attestation(self, block, slot, participants, payload_present):
        """
        Deliver an attestation at ``slot`` for ``block`` from the ``participants`` of the slot's
        first committee. ``payload_present`` picks the ``full`` or ``empty`` node of a block from
        an earlier slot.
        """
        spec = self.spec
        state = block.state.copy()
        if state.slot < slot:
            spec.process_slots(state, slot)
        payload_index = None
        if block.slot < slot:
            payload_index = 1 if payload_present else 0
        attestation = get_valid_attestation(
            spec,
            state,
            slot=slot,
            index=0,
            payload_index=payload_index,
            beacon_block_root=block.root,
            filter_participant_set=lambda committee: set(participants) & set(committee),
            signed=True,
        )
        yield from add_attestation(spec, self.store, attestation, self.test_steps)
        self.output_checks()

    def add_votes(self, block, epoch, validators, payload_present):
        """
        Deliver attestations for ``block`` from ``validators``, each at its assigned slot in
        ``epoch``. Every slot must be later than ``block``'s.
        """
        spec = self.spec
        state = block.state.copy()
        start_slot = spec.compute_start_slot_at_epoch(epoch)
        if state.slot < start_slot:
            spec.process_slots(state, start_slot)
        for slot in range(start_slot, start_slot + spec.SLOTS_PER_EPOCH):
            assert slot > block.slot
            slot_state = state.copy()
            if slot_state.slot < slot:
                spec.process_slots(slot_state, slot)
            for index in range(spec.get_committee_count_per_slot(slot_state, epoch)):
                committee = spec.get_beacon_committee(slot_state, slot, index)
                participants = set(validators) & set(committee)
                if len(participants) == 0:
                    continue
                attestation = get_valid_attestation(
                    spec,
                    slot_state,
                    slot=slot,
                    index=index,
                    payload_index=1 if payload_present else 0,
                    beacon_block_root=block.root,
                    filter_participant_set=lambda c, p=participants: p & set(c),
                    signed=True,
                )
                yield from add_attestation(spec, self.store, attestation, self.test_steps)
        self.output_checks()

    def committee(self, block, slot):
        """The first committee at ``slot`` on ``block``'s chain."""
        spec = self.spec
        state = block.state.copy()
        if state.slot < slot:
            spec.process_slots(state, slot)
        return sorted(spec.get_beacon_committee(state, slot, 0))

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
        head = self.head()
        assert head.root == root, "unexpected head root"
        assert head.payload_status == payload_status, "unexpected head payload status"

    def is_optimistic(self, node):
        return self.spec.is_optimistic(self.opt_store, node)


def start(spec, state, test_steps, slot):
    """Create a rig and tick to ``slot``."""
    rig = GloasOptimisticRig(spec, state, test_steps)
    rig.tick(slot)
    return rig
