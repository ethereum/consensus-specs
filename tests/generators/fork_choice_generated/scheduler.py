from dataclasses import dataclass, field


@dataclass(order=True, init=False)
class QueueItem:
    effective_slot: int
    is_attestation: bool
    message: object = field(compare=False)
    dependencies: list = field(compare=False)
    is_from_block: bool = field(compare=False)

    def __init__(self, message, is_attestation, is_from_block=False):
        self.message = message
        self.is_attestation = is_attestation
        if is_attestation:
            data = message.data
            self.effective_slot = data.slot + 1
            self.dependencies = [data.beacon_block_root, data.target.root]
            self.is_from_block = is_from_block
        else:
            block = message.message
            self.effective_slot = block.slot
            self.dependencies = [block.parent_root]
            self.is_from_block = False


class MessageScheduler:
    def __init__(self, spec, anchor_state, anchor_block):
        self.spec = spec
        self.store = spec.get_forkchoice_store(anchor_state, anchor_block)
        self.message_queue = []

    def is_early_message(self, item: QueueItem) -> bool:
        current_slot = self.spec.get_current_slot(self.store)
        return item.effective_slot < current_slot or any(root not in self.store.blocks for root in item.dependencies)
    
    def enque_message(self, item: QueueItem):
        self.message_queue.append(item)
    
    def drain_queue(self, ) -> list[QueueItem]:
        messages = self.message_queue[:]
        self.message_queue.clear()
        return messages
    
    def process_queue(self):
        updated = False
        for item in self.drain_queue():
            if self.is_early_message(item):
                self.enque_message(item)
            else:
                if item.is_attestation:
                    self.process_attestation(item.message)
                else:
                    updated |= self.process_block(item.message)
        return updated

    def purge_queue(self):
        while self.process_queue():
            pass
    
    def process_tick(self, time):
        SECONDS_PER_SLOT = self.spec.config.SECONDS_PER_SLOT
        assert time >= self.store.time
        tick_slot = (time - self.store.genesis_time) // SECONDS_PER_SLOT
        while self.spec.get_current_slot(self.store) < tick_slot:
            previous_time = self.store.genesis_time + (self.spec.get_current_slot(self.store) + 1) * SECONDS_PER_SLOT
            self.spec.on_tick(self.store, previous_time)
            self.purge_queue()

    def process_attestation(self, attestation, is_from_block=False):
        try:
            self.spec.on_attestation(self.store, attestation, is_from_block)
            return True
        except AssertionError:
            item = QueueItem(attestation, True, is_from_block)
            if self.is_early_message(item):
                self.enque_message(item)
            return False

    def process_slashing(self, slashing):
        try:
            self.spec.on_attester_slashing(self.store, slashing)
            return True
        except AssertionError:
            return False
    
    def process_block_messages(self, signed_block):
        block = signed_block.message
        for attestation in block.body.attestations:
            self.process_attestation(attestation, is_from_block=True)
        for attester_slashing in block.body.attester_slashings:
            self.process_slashing(attester_slashing)

    def process_block(self, signed_block):
        try:
            self.spec.on_block(self.store, signed_block)
            valid = True
        except AssertionError:
            item = QueueItem(signed_block, False)
            if self.is_early_message(item):
                self.enque_message(item)
            valid = False
        if valid:
            self.purge_queue()
            self.process_block_messages(signed_block)
        return valid
