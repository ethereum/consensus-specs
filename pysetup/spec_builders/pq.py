from pysetup.constants import PQ

from .base import BaseSpecBuilder


class PQSpecBuilder(BaseSpecBuilder):
    fork: str = PQ

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.eip8483 import {preset_name} as eip8483
from eth_consensus_specs.utils import xmss
"""

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return {
            "G2_POINT_AT_INFINITY",
            "PQ_REGISTRATION_REQUEST_TYPE",
        }

    @classmethod
    def deprecate_presets(cls) -> set[str]:
        return {
            "MAX_ATTESTER_SLASHING_SIZE",
            "MAX_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD",
            "MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE",
            "MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE",
        }

    @classmethod
    def deprecate_containers(cls) -> set[str]:
        return {
            "BuilderPQRegistration",
            "BuilderPQRegistrations",
            "PQRegistration",
            "PQRegistrationRequest",
            "PQRegistrationRequests",
            "PQRegistrations",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "eth_aggregate_pubkeys",
            "eth_fast_aggregate_verify",
            "process_builder_pq_registration_request",
            "process_pq_registration_request",
            "upgrade_attestation_to_gloas",
            "upgrade_attester_slashing_to_gloas",
            "upgrade_indexed_attestation_to_gloas",
            "upgrade_lc_bootstrap_to_gloas",
            "upgrade_lc_finality_update_to_gloas",
            "upgrade_lc_header_to_gloas",
            "upgrade_lc_optimistic_update_to_gloas",
            "upgrade_lc_store_to_gloas",
            "upgrade_lc_update_to_gloas",
            "upgrade_to_eip8483",
        }
