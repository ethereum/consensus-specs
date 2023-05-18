from ruamel.yaml import YAML
from dataclasses import dataclass, field
from typing import Dict
yaml = YAML()


class StateID(str):

    @classmethod
    def Root(cls, root):
        return cls(f"root:{root.hex()}")

    @classmethod
    def Slot(cls, slot):
        return cls(f"slot:{slot}")

    @classmethod
    def Head(cls):
        return cls("head")

    @classmethod
    def Genesis(cls):
        return cls("genesis")

    @classmethod
    def Finalized(cls):
        return cls("finalized")

    @classmethod
    def Justified(cls):
        return cls("justified")


@dataclass(kw_only=True)
class VerifyBeaconStateV2:
    method: str = "BeaconStateV2"
    id: StateID
    fields: Dict = field(default_factory=dict)

    def __post_init__(self):
        self.id = str(self.id)

    def state_root(self, state_root):
        self.fields["state_root"] = state_root.hex()
        return self


yaml.register_class(VerifyBeaconStateV2)
