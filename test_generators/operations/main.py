from gen_base import gen_runner

from deposits import mini_deposits_suite, full_deposits_suite
from proposer_slashing import mini_proposer_slashing_suite, full_proposer_slashing_suite

if __name__ == "__main__":
    gen_runner.run_generator("operations", [
        mini_deposits_suite,
        full_deposits_suite,
        mini_proposer_slashing_suite,
        full_proposer_slashing_suite,
    ])
