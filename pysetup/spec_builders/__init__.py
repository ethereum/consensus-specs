from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .eip8025 import EIP8025SpecBuilder
from .electra import ElectraSpecBuilder
from .fulu import FuluSpecBuilder
from .gloas import GloasSpecBuilder
from .heze import HezeSpecBuilder
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
        GloasSpecBuilder,
        HezeSpecBuilder,
        EIP8025SpecBuilder,
    )
}
