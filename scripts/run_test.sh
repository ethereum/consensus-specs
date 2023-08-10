#! /bin/sh

# Run 'consensus-specs' tests from a container instance.
# *Be sure to launch Docker before running this script.*
#
# It does the below:
#   1. Run pytest for consensus-specs in a container.
#   2. Copy and paste the coverage report.
#   3. Remove all exited containers that use the consensus-specs:<TAG> images.


# Constants
ALL_EXECUTABLE_SPECS=("phase0" "altair" "bellatrix" "capella" "deneb" "eip6110" "whisk")
TEST_PRESET_TYPE=minimal
WORKDIR="//consensus-specs//tests//core//pyspec"
ETH2SPEC_FOLDER_NAME="eth2spec"
CONTAINER_NAME="consensus-specs-tests"

COV_HTML_OUT=.htmlcov

# Default flag values
version=latest
number_of_core=4

# Generates coverage scope
coverage_scope=()
for spec in "${ALL_EXECUTABLE_SPECS[@]}"
do
    coverage_scope+=("--cov=${ETH2SPEC_FOLDER_NAME}.${spec}.${TEST_PRESET_TYPE}")
done

display_help() {
  echo "Run 'consensus-specs' tests from a container instance."
  echo "Be sure to launch Docker before running this script."
  echo
  echo "Syntax: run_test [-v TAG | -n NUMBER_OF_CORE | -h HELP]"
  echo "-v      Specify the image tag for consensus-specs."
  echo "-n      Specify the number of core to run tests."
  echo "-h      Get helps."
}

# Parse provided flags
while getopts v:n:h flag
do
    case "${flag}" in
        v) version=$OPTARG;;
        n) number_of_core=$OPTARG;;
        h) display_help && $SHELL;;
        \?) echo "not valid -$OPTARG" && $SHELL;;
    esac
done

# Stop and remove the 'consensus-specs-dockerfile-test' container.
# If this container doesn't exist, then a error message is printed
#  (but the process is not stopped).
cleanup() {
  echo "Stop and remove the 'consensus-specs-tests' container."
  docker stop $CONTAINER_NAME || true && docker rm $CONTAINER_NAME || true
}

# Copy the coverage report from the container to the local
copy_coverage_report() {
  docker cp $$CONTAINER_NAME:$WORKDIR/$COV_HTML_OUT ./$COV_HTML_OUT
}

cleanup
# Equivalent to `make test`
docker run -w $WORKDIR --name $CONTAINER_NAME consensus-specs:$version \
    pytest -n $number_of_core --disable-bls $coverage_scope --cov-report="html:${COV_HTML_OUT}" --cov-branch eth2spec

# Get coverage report form container instance
$(copy_coverage_report)
# Only clean container after user exit console
trap cleanup EXIT

$SHELL