from gen_base import gen_runner

from deposits import mini_deposits_suite, full_deposits_suite

if __name__ == "__main__":
    gen_runner.run_generator("operations", [
        mini_deposits_suite,
        full_deposits_suite
    ])
