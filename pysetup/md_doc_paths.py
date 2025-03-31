import os

from .constants import (
    PHASE0,
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
    EIP6800,
    EIP7441,
    EIP7732,
    EIP7805,
)


PREVIOUS_FORK_OF = {
    PHASE0: None,
    ALTAIR: PHASE0,
    BELLATRIX: ALTAIR,
    CAPELLA: BELLATRIX,
    DENEB: CAPELLA,
    ELECTRA: DENEB,
    FULU: ELECTRA,
    EIP6800: DENEB,
    EIP7441: CAPELLA,
    EIP7732: ELECTRA,
    EIP7805: ELECTRA,
}

ALL_FORKS = list(PREVIOUS_FORK_OF.keys())

IGNORE_SPEC_FILES = [
    "specs/phase0/deposit-contract.md"
]

EXTRA_SPEC_FILES = {
    BELLATRIX: "sync/optimistic.md"
}

DEFAULT_ORDER = (
    "beacon-chain",
    "polynomial-commitments",
)


def is_post_fork(a, b) -> bool:
    """
    Returns true if fork a is after b, or if a == b
    """
    if a == b:
        return True

    curr_fork = a
    while curr_fork := PREVIOUS_FORK_OF.get(curr_fork):
        if curr_fork == b:
            return True
    return False


def get_fork_directory(fork):
    for directory in (f'specs/{fork}', f'specs/_features/{fork}'):
        if os.path.exists(directory):
            return directory
    raise FileNotFoundError(f"No directory found for fork: {fork}")


def sort_key(s):
    for index, key in enumerate(DEFAULT_ORDER):
        if key in s:
            return (index, s)
    return (len(DEFAULT_ORDER), s)


def get_md_doc_paths(spec_fork: str) -> str:
    md_doc_paths = []

    for fork in ALL_FORKS:
        if is_post_fork(spec_fork, fork):
            # Append all files in fork directory recursively
            fork_dir = get_fork_directory(fork)
            for root, _, files in os.walk(fork_dir):
                filepaths = [os.path.join(root, filename) for filename in files 
                             if filename.endswith('.md')]
                
                for filepath in sorted(filepaths, key=sort_key):
                    if filepath not in IGNORE_SPEC_FILES:
                        md_doc_paths.append(filepath)
            
            # Append extra files if any
            if extra_file := EXTRA_SPEC_FILES.get(fork):
                md_doc_paths.append(extra_file)

    return '\n'.join(md_doc_paths) + '\n'
