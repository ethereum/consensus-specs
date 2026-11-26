"""
Generate the XMSS public keys of the test private keys in keys.py, which tests
load from the file written here.

Usage (from the project root):
    .venv/bin/python scripts/gen_xmss_pubkeys.py
"""

from pathlib import Path

from eth_consensus_specs.utils import xmss

PROJECT_DIR = Path(__file__).parent.parent
HELPERS_DIR = PROJECT_DIR / "tests/core/pyspec/eth_consensus_specs/test/helpers"
PUBKEYS_PATH = HELPERS_DIR / "xmss_pubkeys.bin"

XMSS_KEY_COUNT = 1024


if __name__ == "__main__":
    with open(PUBKEYS_PATH, "wb") as f:
        for seed in range(1, XMSS_KEY_COUNT + 1):
            f.write(xmss.SkToPk(seed))
            if seed % 128 == 0:
                print(f"{seed}/{XMSS_KEY_COUNT}", flush=True)
