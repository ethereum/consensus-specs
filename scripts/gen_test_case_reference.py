"""
Automatically generate markdown documentation for all test modules
via mkdocstrings.
"""

import contextlib
import io
import logging
import os
import re
import textwrap
from pathlib import Path
from string import Template
from typing import Tuple

import mkdocs_gen_files
import pytest
from git import Repo

from eth2spec.test.helpers.constants import ALL_PHASES  # not working yet

GEN_TEST_PATH = "tests/core/pyspec/eth2spec/test"
source_directory = Path(GEN_TEST_PATH)
non_test_files_to_include = []  # __init__.py is treated separately

# Locate to `consensus-specs` to determine the repository (GitPython)
os.chdir("../")

logger = logging.getLogger("mkdocs")


GENERATE_FIXTURES_DEPLOYED = Template(
    textwrap.dedent(
        """
        !!! example "Launch these test cases $additional_title with:"
            ```console
            pytest $pytest_test_path
            ```

        """
    )
)

GENERATE_FIXTURES_DEVELOPMENT = Template(
    textwrap.dedent(
        """
        !!! example "Launch these test cases for $fork with:"
            $fork only:
            ```console
            pytest $pytest_test_path --fork=$fork
            ```
            
            For all forks up to and including $fork:
            ```console
            pytest $pytest_test_path $all_fork_before
            ```
        """
    )
)

# mkdocstrings filter doc:
# https://mkdocstrings.github.io/python/usage/configuration/members/#filters
MARKDOWN_TEMPLATE = Template(
    textwrap.dedent(
        """
        # $title

        Documentation for [`$pytest_test_path`]($module_github_url).

        $generate_fixtures_deployed
        $generate_fixtures_development
        ::: $package_name
            options:
                filters: ["^[tT]est*|^Spec*"]
        """
    )
)

MARKDOWN_TEST_CASES_TEMPLATE = Template(
    textwrap.dedent(
        """
        # $title

        !!! example "Test cases generated from `$pytest_test_path`"
            Parametrized test cases generated from the test module [`$pytest_test_path`]($module_github_url):

            ```
            $collect_only_output
            ```

            This output was extracted from the result of:

            ```console
            $collect_only_command
            ```
        """  # noqa: E501
    )
)


def get_script_relative_path():  # noqa: D103
    script_path = os.path.abspath(__file__)
    current_directory = os.getcwd()
    return os.path.relpath(script_path, current_directory)


def snake_to_capitalize(s: str) -> str:  # noqa: D103
    return " ".join(word.capitalize() for word in s.split("_"))


def copy_file(source_file, destination_file):
    """
    Copy a file by writing it's contents using mkdocs_gen_files.open()
    """
    with open(source_file, "r") as source:
        with mkdocs_gen_files.open(destination_file, "w") as destination:
            for line in source:
                destination.write(line)


def run_collect_only(test_path: Path = source_directory) -> Tuple[str, str]:
    """
    Run pytest with --collect-only to get a list of executed tests.

    Args:
        test_path: The directory or test module to collect tests for.
            Defaults to source_directory.

    Returns:
        str: The command used to collect the tests.
        str: A list of the collected tests.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        pytest.main(["--import-mode=importlib", "--collect-only", "-q", str(test_path)])
    output = buffer.getvalue()
    collect_only_command = (
        f"pytest --import-mode=importlib --collect-only -q {test_path}"
    )
    # strip out the test module
    output_lines = [
        line.split("::")[1]
        for line in output.split("\n")
        if line.startswith("tests/") and "::" in line
    ]
    # prefix with required indent for admonition in MARKDOWN_TEST_CASES_TEMPLATE
    collect_only_output = "\n".join("    " + line for line in output_lines)
    collect_only_output = collect_only_output[4:]  # strip out indent for first line
    return collect_only_command, collect_only_output


def generate_github_url(file_path, branch_or_commit_or_tag="main") -> str:
    """
    Generate a link to a source file in Github.
    """
    base_url = "https://github.com"
    username = "ethereum"
    repository = "consensus-specs"
    if re.match(
        r"^v[0-9]{1,2}\.[0-9]{1,3}\.[0-9]{1,3}(a[0-9]+|b[0-9]+|rc[0-9]+)?$",
        branch_or_commit_or_tag,
    ):
        return f"{base_url}/{username}/{repository}/tree/{branch_or_commit_or_tag}/{file_path}"
    return (
        f"{base_url}/{username}/{repository}/blob/{branch_or_commit_or_tag}/{file_path}"
    )


def get_current_commit_hash_or_tag(repo_path="."):
    """
    Get the latest commit hash or tag from the clone where doc is being built.
    """
    repo = Repo(repo_path)
    try:
        # Get the tag that points to the current commit
        current_tag = next((tag for tag in repo.tags if tag.commit == repo.head.commit))
        return current_tag.name
    except StopIteration:
        # If there are no tags that point to the current commit, return the commit hash
        return repo.head.commit.hexsha


def get_current_commit_hash(repo_path="."):
    """
    Get the latest commit hash from the clone where doc is being built.
    """
    repo = Repo(repo_path)
    return repo.head.commit.hexsha


COMMIT_HASH_OR_TAG = get_current_commit_hash_or_tag()


def non_recursive_os_walk(top_dir):
    """
    Return the output of os.walk for the top-level directory.
    """
    for root, directories, files in os.walk(top_dir):
        return [(root, directories, files)]


# The nav section for test doc will get built here
nav = mkdocs_gen_files.Nav()

fork_directories = [source_directory / fork.lower() for fork in ALL_PHASES]
fork_directories.reverse()
all_directories = [
    directory for directory in fork_directories if os.path.exists(directory)
]
all_directories.insert(0, source_directory)

# Loop over directories here instead of walking tests/ to ensure we
# get a reverse chronological listing of forks in the nav bar.
for directory in all_directories:
    if directory is source_directory:
        # Process files within tests/ but don't walk it recursively.
        walk_directory_output = non_recursive_os_walk(directory)
    else:
        # Walk each tests/fork/ directory recursively.
        # sorted() is a bit of a hack to order nav content for each fork
        walk_directory_output = sorted(os.walk(directory))
    for root, _, files in walk_directory_output:
        if "__pycache__" in root:
            continue

        markdown_files = [filename for filename in files if filename.endswith(".md")]
        python_files = [filename for filename in files if filename.endswith(".py")]

        test_dir_relative_path = Path(root.split("eth2spec")[-1][1:])

        # Process Markdown files first, then Python files for nav section ordering
        for file in markdown_files:
            source_file = Path(root) / file
            suffix = ""
            if file.lower() == "readme.md":
                # If there's a file called readme python-mkdocstrings will take this as the
                # page's index.md. This will subsequently get overwritten by the `__init__.py`.
                # Hack, add an underscore to differentiate the file and include it in the doc.
                suffix = "_"
            basename, extension = os.path.splitext(file)
            file = f"{basename}{suffix}.{extension}"
            output_file_path = test_dir_relative_path / file
            nav_path = "Test Case Reference" / test_dir_relative_path / basename
            copy_file(source_file, output_file_path)
            nav_tuple = tuple(snake_to_capitalize(part) for part in nav_path.parts)
            # nav_tuple = tuple(apply_name_filters(part) for part in nav_tuple)
            nav[nav_tuple] = str(output_file_path)

        for file in sorted(python_files):
            output_file_path = Path("undefined")

            if file == "__init__.py":
                output_file_path = test_dir_relative_path / "index.md"
                nav_path = "Test Case Reference" / test_dir_relative_path
                package_name = root.replace(os.sep, ".")
                pytest_test_path = root
            elif file.startswith("test_") or file in non_test_files_to_include:
                file_no_ext = os.path.splitext(file)[0]
                output_file_path = test_dir_relative_path / file_no_ext / "index.md"
                nav_path = "Test Case Reference" / test_dir_relative_path / file_no_ext
                package_name = os.path.join(root, file_no_ext).replace(os.sep, ".")
                pytest_test_path = os.path.join(root, file)
            else:
                continue

            nav_tuple = tuple(snake_to_capitalize(part) for part in nav_path.parts)
            nav[nav_tuple] = str(output_file_path)
            markdown_title = nav_tuple[-1]

            if file.startswith("test_"):
                collect_only_command, collect_only_output = run_collect_only(
                    test_path=pytest_test_path
                )
                if not collect_only_output:
                    logger.warning(
                        "%s collect_only_output for %s is empty", get_script_relative_path(), file
                    )
                test_cases_output_file_path = (
                    Path(os.path.splitext(output_file_path)[0]) / "test_cases.md"
                )
                nav[(*nav_tuple, "Test Cases")] = str(test_cases_output_file_path)
                with mkdocs_gen_files.open(test_cases_output_file_path, "w") as f:
                    f.write(
                        MARKDOWN_TEST_CASES_TEMPLATE.substitute(
                            title=f"{markdown_title} - Test Cases",
                            pytest_test_path=pytest_test_path,
                            module_github_url=generate_github_url(
                                pytest_test_path,
                                branch_or_commit_or_tag=COMMIT_HASH_OR_TAG,
                            ),
                            collect_only_command=collect_only_command,
                            collect_only_output=collect_only_output,
                        )
                    )

            if root == GEN_TEST_PATH:
                # special case, the root tests/ directory
                generate_fixtures_deployed = GENERATE_FIXTURES_DEPLOYED.substitute(
                    pytest_test_path=pytest_test_path,
                    additional_title=" for all forks deployed to mainnet",
                )
                generate_fixtures_development = (
                    GENERATE_FIXTURES_DEVELOPMENT.substitute(
                        pytest_test_path=pytest_test_path,
                        fork=ALL_PHASES[0],
                        all_fork_before="",
                    )
                )
            elif file in non_test_files_to_include:
                generate_fixtures_deployed = ""
                generate_fixtures_development = ""
            elif dev_forks := [
                fork for fork in ALL_PHASES if fork.lower() in root.lower()
            ]:
                assert len(dev_forks) == 1
                # Select all phases before (included) the dev_forks
                all_test_phases = ALL_PHASES[: ALL_PHASES.index(dev_forks[0]) + 1]
                generate_fixtures_deployed = ""
                generate_fixtures_development = (
                    GENERATE_FIXTURES_DEVELOPMENT.substitute(
                        pytest_test_path=pytest_test_path,
                        fork=dev_forks[0],
                        all_fork_before="--fork=" + " --fork=".join(all_test_phases),
                    )
                )
            else:
                generate_fixtures_deployed = GENERATE_FIXTURES_DEPLOYED.substitute(
                    pytest_test_path=pytest_test_path, additional_title=""
                )
                generate_fixtures_development = ""

            with mkdocs_gen_files.open(output_file_path, "w") as f:
                f.write(
                    MARKDOWN_TEMPLATE.substitute(
                        title=markdown_title,
                        package_name=package_name,
                        generate_fixtures_deployed=generate_fixtures_deployed,
                        generate_fixtures_development=generate_fixtures_development,
                        module_github_url=generate_github_url(
                            pytest_test_path, branch_or_commit_or_tag=COMMIT_HASH_OR_TAG
                        ),
                        pytest_test_path=pytest_test_path,
                    )
                )
