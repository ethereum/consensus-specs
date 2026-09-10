from pysetup.constants import DENEB

from .base import BaseSpecBuilder


class DenebSpecBuilder(BaseSpecBuilder):
    fork: str = DENEB

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.capella import {preset_name} as capella
from eth_consensus_specs.utils import kzg
"""

    @classmethod
    def sundry_functions(cls) -> str:
        return """
def retrieve_blobs_and_proofs(beacon_block_root: Root) -> Tuple[Sequence[Blob], Sequence[KZGProof]]:
    return [], []
"""

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


EXECUTION_ENGINE = NoopExecutionEngine()"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_lc_bootstrap_to_capella",
            "upgrade_lc_finality_update_to_capella",
            "upgrade_lc_header_to_capella",
            "upgrade_lc_optimistic_update_to_capella",
            "upgrade_lc_store_to_capella",
            "upgrade_lc_update_to_capella",
            "upgrade_to_capella",
        }

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> dict[str, str]:
        return {
            "KZG_COMMITMENT_INCLUSION_PROOF_DEPTH": spec_object.preset_vars[
                "KZG_COMMITMENT_INCLUSION_PROOF_DEPTH"
            ].value,
        }
