from pysetup.constants import EIP8369

from .base import BaseSpecBuilder


class EIP8369SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8369

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

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
                                  payload_attributes: PayloadAttributes | None,
                                  custody_columns: CustodyColumnBits | None) -> PayloadId | None:
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

    def get_inclusion_list(self: ExecutionEngine) -> GetInclusionListResponse:
        raise NotImplementedError("no default inclusion list production")

    def is_inclusion_list_satisfied(self: ExecutionEngine,
                                    execution_payload: ExecutionPayload,
                                    inclusion_lists: Sequence[Sequence[Transaction]],
                                    inclusion_list_claims: Sequence[InclusionListClaim]) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {"get_inclusion_list_transactions", "upgrade_to_heze"}
