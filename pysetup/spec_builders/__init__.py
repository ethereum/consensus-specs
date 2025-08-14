from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .eip6800 import EIP6800SpecBuilder
from .eip7441 import EIP7441SpecBuilder
from .eip7805 import EIP7805SpecBuilder
from .electra import ElectraSpecBuilder
from .fulu import FuluSpecBuilder
from .gloas import GloasSpecBuilder
from .phase0 import Phase0SpecBuilder

spec_builders = {
    builder.fork: builder
    for builder in (
        Phase0SpecBuilder,
        AltairSpecBuilder,
        BellatrixSpecBuilder,
        CapellaSpecBuilder,
        DenebSpecBuilder,
        ElectraSpecBuilder,
        FuluSpecBuilder,
        EIP6800SpecBuilder,
        EIP7441SpecBuilder,
        GloasSpecBuilder,
        EIP7805SpecBuilder,
    )
}
