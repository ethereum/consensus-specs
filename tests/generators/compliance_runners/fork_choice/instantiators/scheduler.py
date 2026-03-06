from dataclasses import dataclass, field
from enum import Enum

from .helpers import payload_attestation_to_messages


class QueueItemKind(Enum):
    BLOCK = 0
    ATTESTATION = 1
    EXECUTION_PAYLOAD = 2
    PAYLOAD_ATTESTATION = 3


@dataclass(order=True, init=False)
class QueueItem:
    effective_slot: int
    kind: QueueItemKind
    message: object = field(compare=False)
    dependencies: list = field(compare=False)
    is_from_block: bool = field(compare=False)

    def __init__(self, message, kind: QueueItemKind, is_from_block=False):
        self.message = message
        self.kind = kind
        if kind == QueueItemKind.ATTESTATION:
            data = message.data
            self.effective_slot = data.slot + 1
            self.dependencies = [data.beacon_block_root, data.target.root]
            self.is_from_block = is_from_block
        elif kind == QueueItemKind.BLOCK:
            block = message.message
            self.effective_slot = block.slot
            self.dependencies = [block.parent_root]
            self.is_from_block = False
        elif kind == QueueItemKind.EXECUTION_PAYLOAD:
            payload = message.message
            self.effective_slot = payload.payload.slot_number
            self.dependencies = [payload.beacon_block_root]
            self.is_from_block = False
        else:
            assert kind == QueueItemKind.PAYLOAD_ATTESTATION
            data = message.data
            self.effective_slot = data.slot
            self.dependencies = [data.beacon_block_root]
            self.is_from_block = is_from_block


class MessageScheduler:
    def __init__(self, spec, store):
        self.spec = spec
        self.store = store
        self.message_queue = []

    def is_early_message(self, item: QueueItem) -> bool:
        current_slot = self.spec.get_current_slot(self.store)
        return item.effective_slot > current_slot or any(
            root not in self.store.blocks for root in item.dependencies
        )

    def enque_message(self, item: QueueItem):
        self.message_queue.append(item)

    def drain_queue(
        self,
    ) -> list[QueueItem]:
        messages = self.message_queue[:]
        self.message_queue.clear()
        return messages

    def process_queue(self) -> tuple[bool, list]:
        applied_events = []
        updated = False
        for item in self.drain_queue():
            if self.is_early_message(item):
                self.enque_message(item)
            elif item.kind == QueueItemKind.ATTESTATION:
                if self.process_attestation(item.message):
                    applied_events.append(("attestation", item.message, True))
            elif item.kind == QueueItemKind.BLOCK:
                updated_, events_ = self.process_block(item.message, recovery=True)
                if updated_:
                    updated = True
                    applied_events.extend(events_)
                    assert ("block", item.message, True) in events_
            elif item.kind == QueueItemKind.EXECUTION_PAYLOAD:
                if self.process_payload(item.message):
                    applied_events.append(("execution_payload", item.message, True))
            else:
                assert item.kind == QueueItemKind.PAYLOAD_ATTESTATION
                if self.process_payload_attestation_message(
                    item.message, is_from_block=item.is_from_block
                ):
                    applied_events.append(("payload_attestation", item.message, True))
        return updated, applied_events

    def purge_queue(self) -> list:
        applied_events = []
        while True:
            updated, events = self.process_queue()
            applied_events.extend(events)
            if updated:
                continue
            else:
                return applied_events

    def process_tick(self, time) -> list:
        applied_events = []
        SLOT_DURATION_MS = self.spec.config.SLOT_DURATION_MS
        assert time >= self.store.time
        tick_slot = (time - self.store.genesis_time) * 1000 // SLOT_DURATION_MS
        while self.spec.get_current_slot(self.store) < tick_slot:
            previous_time = (
                self.store.genesis_time
                + (self.spec.get_current_slot(self.store) + 1) * SLOT_DURATION_MS // 1000
            )
            self.spec.on_tick(self.store, previous_time)
            applied_events.append(
                ("tick", previous_time, self.spec.get_current_slot(self.store) < tick_slot)
            )
            applied_events.extend(self.purge_queue())
        return applied_events

    def process_attestation(self, attestation, is_from_block=False):
        try:
            self.spec.on_attestation(self.store, attestation, is_from_block)
            return True
        except AssertionError:
            item = QueueItem(attestation, QueueItemKind.ATTESTATION, is_from_block)
            if self.is_early_message(item):
                self.enque_message(item)
            return False

    def process_slashing(self, slashing):
        try:
            self.spec.on_attester_slashing(self.store, slashing)
            return True
        except AssertionError:
            return False

    def process_payload_attestation_message(self, ptc_message, is_from_block=False):
        try:
            self.spec.on_payload_attestation_message(self.store, ptc_message, is_from_block)
            return True
        except AssertionError:
            item = QueueItem(ptc_message, QueueItemKind.PAYLOAD_ATTESTATION, is_from_block)
            if self.is_early_message(item):
                self.enque_message(item)
            return False

    def process_block_messages(self, signed_block):
        block = signed_block.message
        if hasattr(block.body, "payload_attestations"):
            state = self.store.block_states[block.hash_tree_root()]
            for payload_attestation in block.body.payload_attestations:
                for ptc_message in payload_attestation_to_messages(
                    self.spec, state, payload_attestation
                ):
                    self.process_payload_attestation_message(ptc_message, is_from_block=True)
        for attestation in block.body.attestations:
            self.process_attestation(attestation, is_from_block=True)
        for attester_slashing in block.body.attester_slashings:
            self.process_slashing(attester_slashing)

    def process_block(self, signed_block, recovery=False) -> tuple[bool, list]:
        applied_events = []
        try:
            self.spec.on_block(self.store, signed_block)
            valid = True
            applied_events.append(("block", signed_block, recovery))
        except AssertionError:
            item = QueueItem(signed_block, QueueItemKind.BLOCK)
            if self.is_early_message(item):
                self.enque_message(item)
            valid = False
        if valid:
            applied_events.extend(self.purge_queue())
            self.process_block_messages(signed_block)
        return valid, applied_events
    
    def process_payload(self, signed_payload) -> bool:
        try:
            self.spec.on_execution_payload_envelope(self.store, signed_payload)
            return True
        except AssertionError:
            item = QueueItem(signed_payload, QueueItemKind.EXECUTION_PAYLOAD)
            if self.is_early_message(item):
                self.enque_message(item)
            return False
