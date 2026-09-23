from pysetup.constants import PAYLOAD_REQUEST_CHAIN

from .base import BaseSpecBuilder


class PayloadRequestChainSpecBuilder(BaseSpecBuilder):
    fork: str = PAYLOAD_REQUEST_CHAIN

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.gloas import {preset_name} as gloas
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_to_gloas",
        }

    @classmethod
    def execution_engine_cls(cls) -> str:
        return """
class NoopExecutionEngine(ExecutionEngine):

    def notify_new_payload(self: ExecutionEngine,
                           execution_payload: ExecutionPayload,
                           parent_beacon_block_root: Root,
                           execution_requests_list: Sequence[bytes]) -> bool:
        return True

    def notify_forkchoice_updated(self: ExecutionEngine,
                                  head_block_hash: Hash32,
                                  safe_block_hash: Hash32,
                                  finalized_block_hash: Hash32,
                                  payload_attributes: Optional[PayloadAttributes],
                                  custody_columns: Optional[CustodyColumnBits]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        raise NotImplementedError("no default block production")

    def is_valid_block_hash(self: ExecutionEngine,
                            execution_payload: ExecutionPayload,
                            parent_beacon_block_root: Root,
                            execution_requests_list: Sequence[bytes]) -> bool:
        return True

    def is_valid_versioned_hashes(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
        return True

    def verify_and_notify_new_payload(self: ExecutionEngine,
                                      new_payload_request: NewPayloadRequest) -> bool:
        return True

    def verify_payload_request_chain_root(self: ExecutionEngine,
                                          new_payload_request: NewPayloadRequest,
                                          payload_request_chain_root: Bytes32) -> Optional[bool]:
        return None


EXECUTION_ENGINE = NoopExecutionEngine()"""
