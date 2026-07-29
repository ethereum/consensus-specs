from .coverage import materialize_profile
from .validation import main as validate


def main():
    materialize_profile("standard")
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
