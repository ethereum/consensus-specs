from typing import Dict
from .base import BaseSpecBuilder
from ..constants import ELECTRA


class ElectraSpecBuilder(BaseSpecBuilder):
    fork: str = ELECTRA

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {
            'FINALIZED_ROOT_GINDEX_ELECTRA': 'GeneralizedIndex(169)',
            'CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA': 'GeneralizedIndex(86)',
            'NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA': 'GeneralizedIndex(87)',
        }
