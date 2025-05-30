from typing import Dict

from ..constants import ELECTRA
from .base import BaseSpecBuilder


class ElectraSpecBuilder(BaseSpecBuilder):
    fork: str = ELECTRA

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth2spec.deneb import {preset_name} as deneb
from eth2spec.utils.ssz.ssz_impl import ssz_serialize, ssz_deserialize
"""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {
            "FINALIZED_ROOT_GINDEX_ELECTRA": "GeneralizedIndex(169)",
            "CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA": "GeneralizedIndex(86)",
            "NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA": "GeneralizedIndex(87)",
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
                                  payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        # pylint: disable=unused-argument
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


EXECUTION_ENGINE = NoopExecutionEngine()"""
