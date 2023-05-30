from .constants import (
    PHASE0,
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    EIP6110,
)


def get_md_doc_paths(spec_fork: str) -> str:
    md_doc_paths = ""
    if spec_fork in (PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, EIP6110):
        md_doc_paths += """
            specs/phase0/beacon-chain.md
            specs/phase0/fork-choice.md
            specs/phase0/validator.md
            specs/phase0/weak-subjectivity.md
            specs/phase0/p2p-interface.md
        """
    if spec_fork in (ALTAIR, BELLATRIX, CAPELLA, DENEB, EIP6110):
        md_doc_paths += """
            specs/altair/light-client/full-node.md
            specs/altair/light-client/light-client.md
            specs/altair/light-client/p2p-interface.md
            specs/altair/light-client/sync-protocol.md
            specs/altair/beacon-chain.md
            specs/altair/bls.md
            specs/altair/fork.md
            specs/altair/validator.md
            specs/altair/p2p-interface.md
        """
    if spec_fork in (BELLATRIX, CAPELLA, DENEB, EIP6110):
        md_doc_paths += """
            specs/bellatrix/beacon-chain.md
            specs/bellatrix/fork.md
            specs/bellatrix/fork-choice.md
            specs/bellatrix/validator.md
            specs/bellatrix/p2p-interface.md
            sync/optimistic.md
        """
    if spec_fork in (CAPELLA, DENEB, EIP6110):
        md_doc_paths += """
            specs/capella/light-client/fork.md
            specs/capella/light-client/full-node.md
            specs/capella/light-client/p2p-interface.md
            specs/capella/light-client/sync-protocol.md
            specs/capella/beacon-chain.md
            specs/capella/fork.md
            specs/capella/fork-choice.md
            specs/capella/validator.md
            specs/capella/p2p-interface.md
        """
    if spec_fork in (DENEB, EIP6110):
        md_doc_paths += """
            specs/deneb/light-client/fork.md
            specs/deneb/light-client/full-node.md
            specs/deneb/light-client/p2p-interface.md
            specs/deneb/light-client/sync-protocol.md
            specs/deneb/beacon-chain.md
            specs/deneb/fork.md
            specs/deneb/fork-choice.md
            specs/deneb/polynomial-commitments.md
            specs/deneb/p2p-interface.md
            specs/deneb/validator.md
        """
    if spec_fork == EIP6110:
        md_doc_paths += """
            specs/_features/eip6110/light-client/fork.md
            specs/_features/eip6110/light-client/full-node.md
            specs/_features/eip6110/light-client/p2p-interface.md
            specs/_features/eip6110/light-client/sync-protocol.md
            specs/_features/eip6110/beacon-chain.md
            specs/_features/eip6110/fork.md
        """
    return md_doc_paths
