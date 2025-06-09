import os

from .constants import (
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    EIP6800,
    EIP7441,
    EIP7732,
    EIP7805,
    ELECTRA,
    FULU,
    PHASE0,
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

IGNORE_SPEC_FILES = ["specs/phase0/deposit-contract.md"]

EXTRA_SPEC_FILES = {BELLATRIX: "sync/optimistic.md"}

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

    prev_fork = PREVIOUS_FORK_OF[a]
    if prev_fork == b:
        return True
    elif prev_fork is None:
        return False
    else:
        return is_post_fork(prev_fork, b)


def get_fork_directory(fork):
    dir1 = f"specs/{fork}"
    if os.path.exists(dir1):
        return dir1
    dir2 = f"specs/_features/{fork}"
    if os.path.exists(dir2):
        return dir2
    raise FileNotFoundError(f"No directory found for fork: {fork}")


def sort_key(s):
    for index, key in enumerate(DEFAULT_ORDER):
        if key in s:
            return (index, s)
    return (len(DEFAULT_ORDER), s)


def get_md_doc_paths(spec_fork: str) -> str:
    md_doc_paths = ""

    for fork in ALL_FORKS:
        if is_post_fork(spec_fork, fork):
            # Append all files in fork directory recursively
            for root, _, files in os.walk(get_fork_directory(fork)):
                filepaths = []
                for filename in files:
                    filepath = os.path.join(root, filename)
                    filepaths.append(filepath)
                for filepath in sorted(filepaths, key=sort_key):
                    if filepath.endswith(".md") and filepath not in IGNORE_SPEC_FILES:
                        md_doc_paths += filepath + "\n"
            # Append extra files if any
            if fork in EXTRA_SPEC_FILES:
                md_doc_paths += EXTRA_SPEC_FILES[fork] + "\n"

    return md_doc_paths
