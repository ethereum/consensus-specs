from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .eip7716 import EIP7716SpecBuilder
from .eip8025 import EIP8025SpecBuilder
from .eip8148 import EIP8148SpecBuilder
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
        EIP7716SpecBuilder,
        EIP8025SpecBuilder,
        EIP8148SpecBuilder,
    )
}
