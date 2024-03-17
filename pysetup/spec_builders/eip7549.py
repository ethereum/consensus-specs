from .base import BaseSpecBuilder
from ..constants import EIP7549


class EIP7549SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7549

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
'''
