from .base import BaseSpecBuilder
from ..constants import EIP7547


class EIP7547SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7547

    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def retrieve_inclusion_list(slot: Slot, proposer_index: ValidatorIndex) -> InclusionList:
    # pylint: disable=unused-argument
    ...
'''

    @classmethod
    def execution_engine_cls(cls) -> str:
        return """
class NoopExecutionEngine(ExecutionEngine):
    def notify_new_payload(self: ExecutionEngine,
                           execution_payload: ExecutionPayload,
                           parent_beacon_block_root: Root) -> bool:
        return True
    def notify_forkchoice_updated(self: ExecutionEngine,
                                  head_block_hash: Hash32,
                                  safe_block_hash: Hash32,
                                  finalized_block_hash: Hash32,
                                  payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
        pass
    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        # pylint: disable=unused-argument
        raise NotImplementedError("no default block production")
    def is_valid_block_hash(self: ExecutionEngine,
                            execution_payload: ExecutionPayload,
                            parent_beacon_block_root: Root) -> bool:
        return True
    def is_valid_versioned_hashes(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
        return True
    def verify_and_notify_new_payload(self: ExecutionEngine,
                                      new_payload_request: NewPayloadRequest) -> bool:
        return True
    def notify_new_inclusion_list(self: ExecutionEngine,
                                  inclusion_list_request: NewInclusionListRequest) -> bool:
        return True
    def get_execution_inclusion_list(self: ExecutionEngine, parent_block_hash: Root) -> GetInclusionListResponse:
        return GetInclusionListResponse()
EXECUTION_ENGINE = NoopExecutionEngine()"""

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''
