"""
Automatically generate markdown documentation for all test modules
via mkdocstrings.
"""

import contextlib
import io
import logging
import os
import re
import sys
import textwrap
from pathlib import Path
from string import Template
from typing import Tuple

import mkdocs_gen_files
import pytest
from git import Repo


from core.pyspec.eth2spec.test.helpers.constants import ALL_PHASES

logger = logging.getLogger("mkdocs")

GEN_TEST_PATH = "tests\\core\\pyspec\\eth2spec\\test"
source_directory = Path(GEN_TEST_PATH)
target_dir = Path(GEN_TEST_PATH)
non_test_files_to_include = []  # __init__.py is treated separately


def get_script_relative_path():  # noqa: D103
    script_path = os.path.abspath(__file__)
    current_directory = os.getcwd()
    return os.path.relpath(script_path, current_directory)


"""
The following check that allows deactivation of the Test Case Reference
doc generation is no longer strictly necessary - it was a workaround for
a problem who's root cause has been solved. The code is left, however,
as it could still serve a purpose if we have many more test cases
and test doc gen becomes very time consuming.

If test doc gen is disabled, then it will not appear at all in the
output doc and all incoming links to it will generate a warning.
"""
if os.environ.get("CI") != "true":  # always generate in ci/cd
    enabled_env_var_name = "SPEC_TESTS_AUTO_GENERATE_FILES"
    script_name = get_script_relative_path()
    if os.environ.get(enabled_env_var_name) != "false":
        logger.info(f"{script_name}: generating 'Test Case Reference' doc")
        logger.info(
            f"{script_name}: set env var {enabled_env_var_name} to 'false' and re-run "
            "`mkdocs serve` or `mkdocs build` to  disable 'Test Case Reference' doc generation"
        )
    else:
        logger.warning(
            f"{script_name}: skipping automatic generation of 'Test Case Reference' doc"
        )
        logger.info(
            f"{script_name}: set env var {enabled_env_var_name} to 'true' and re-run"
            "`mkdocs serve` or `mkdocs build` to generate 'Test Case Reference' doc"
        )
        sys.exit(0)

GENERATE_FIXTURES_DEPLOYED = Template(
    textwrap.dedent(
        """
        !!! example "Generate fixtures for these test cases $additional_title with:"
            ```console
            pytest -v $pytest_test_path
            ```

        """
    )
)

GENERATE_FIXTURES_DEVELOPMENT = Template(
    textwrap.dedent(
        """
        !!! example "Generate fixtures for these test cases for $fork with:"
            $fork only:
            ```console
            pytest -v $pytest_test_path --fork=$fork
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

#            options:
#              filters: ["!^_[^_]", "![A-Z]{2,}", "!pytestmark"]


def apply_name_filters(input_string: str):
    """
    Apply a list of regexes to names used in the nav section to clean
    up nav title names.
    """
    regexes = [
        # (r"^Test ", ""),
        (r"vm", "VM"),
        # TODO: enable standard formatting for all opcodes.
        (r"Dup", "DUP"),
        (r"Chainid", "CHAINID"),
        (r"acl", "ACL"),
        (r"eips", "EIPs"),
        (r"eip-?([1-9]{1,5})", r"EIP-\1"),
    ]

    for pattern, replacement in regexes:
        input_string = re.sub(pattern, replacement, input_string, flags=re.IGNORECASE)

    return input_string


def snake_to_capitalize(s):  # noqa: D103
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
        pytest.main(["--collect-only", "-q", str(test_path)])
    output = buffer.getvalue()
    collect_only_command = f"pytest --collect-only -q {test_path}"
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


def generate_github_url(file_path, branch_or_commit_or_tag="main"):
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
    else:
        return f"{base_url}/{username}/{repository}/blob/{branch_or_commit_or_tag}/{file_path}"


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
all_directories = [directory for directory in fork_directories if os.path.exists(directory)]
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

        test_dir_relative_path = Path(root).relative_to("tests")
        output_directory = target_dir / test_dir_relative_path

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
            output_file_path = output_directory / file
            nav_path = "Test Case Reference" / test_dir_relative_path / basename
            copy_file(source_file, output_file_path)
            nav_tuple = tuple(snake_to_capitalize(part) for part in nav_path.parts)
            nav_tuple = tuple(apply_name_filters(part) for part in nav_tuple)
            nav[nav_tuple] = str(output_file_path)

        for file in sorted(python_files):
            output_file_path = Path("undefined")

            if file == "__init__.py":
                output_file_path = output_directory / "index.md"
                nav_path = "Test Case Reference" / test_dir_relative_path
                package_name = root.replace(os.sep, ".")
                pytest_test_path = root
            elif file.startswith("test_") or file in non_test_files_to_include:
                file_no_ext = os.path.splitext(file)[0]
                output_file_path = output_directory / file_no_ext / "index.md"
                nav_path = "Test Case Reference" / test_dir_relative_path / file_no_ext
                package_name = os.path.join(root, file_no_ext).replace(os.sep, ".")
                pytest_test_path = os.path.join(root, file)
            else:
                continue

            nav_tuple = tuple(snake_to_capitalize(part) for part in nav_path.parts)
            nav_tuple = tuple(apply_name_filters(part) for part in nav_tuple)
            nav[nav_tuple] = str(output_file_path)
            markdown_title = nav_tuple[-1]

            if file.startswith("test_"):
                collect_only_command, collect_only_output = run_collect_only(
                    test_path=pytest_test_path
                )
                if not collect_only_output:
                    logger.warning(f"{script_name} collect_only_output for {file} is empty")
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
                                pytest_test_path, branch_or_commit_or_tag=COMMIT_HASH_OR_TAG
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
                generate_fixtures_development = GENERATE_FIXTURES_DEVELOPMENT.substitute(
                    pytest_test_path=pytest_test_path, fork=ALL_PHASES[0]
                )
            elif file in non_test_files_to_include:
                generate_fixtures_deployed = ""
                generate_fixtures_development = ""
            elif dev_forks := [fork for fork in ALL_PHASES if fork.lower() in root.lower()]:
                assert len(dev_forks) == 1
                generate_fixtures_deployed = ""
                generate_fixtures_development = GENERATE_FIXTURES_DEVELOPMENT.substitute(
                    pytest_test_path=pytest_test_path, fork=dev_forks[0]
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
# with mkdocs_gen_files.open(navigation_file, "a") as nav_file:
#     nav_file.writelines(nav.build_literate_nav())