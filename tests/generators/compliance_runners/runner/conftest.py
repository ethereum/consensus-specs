"""Command-line options for independent vector replay."""


def pytest_addoption(parser):
    group = parser.getgroup("compliance replay")
    group.addoption("--test-dir", action="append", help="Vector root (repeatable)")
    group.addoption("--kind", choices=("state_transition", "fork_choice"), default=None)
    group.addoption("--start", type=int, default=None)
    group.addoption("--limit", type=int, default=None)
