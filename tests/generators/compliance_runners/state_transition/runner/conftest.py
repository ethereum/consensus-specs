def pytest_addoption(parser):
    parser.addoption(
        "--test-dir",
        action="append",
        default=None,
        help=("Directory containing generated state-transition compliance tests. Can be repeated."),
    )
    parser.addoption(
        "--start",
        type=int,
        default=None,
        help="Start index (0-based) into the generated test list.",
    )
    parser.addoption(
        "--limit",
        type=int,
        default=None,
        help="Limit number of generated tests to validate.",
    )
