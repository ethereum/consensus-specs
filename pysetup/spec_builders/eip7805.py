from .base import BaseSpecBuilder
from ..constants import EIP7805


class EIP7805SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7805
