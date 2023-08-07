# /bin/sh

# Run 'consensus-specs' tests from a container instance
# Be sure to launch Docker before running this script

# Constants
ALL_EXECUTABLE_SPECS=("phase0" "altair" "bellatrix" "capella" "deneb" "eip6110" "whisk")
TEST_PRESET_TYPE=minimal
WORKDIR="//consensus-specs//tests//core//pyspec"

COV_HTML_OUT=.htmlcov

# Default flag values
version=latest
number_of_core=4

# Generates coverage scope
name="eth2spec"
coverage_scope=()
for spec in "${ALL_EXECUTABLE_SPECS[@]}"
do
    coverage_scope+=("--cov=${name}.${spec}.${TEST_PRESET_TYPE}")
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

# Get IDs of container that run the image `consensus-specs:$version` and are exited.
get_container_name() {
  echo $(docker ps -a -q --filter ancestor="consensus-specs:$version" --filter status="exited" --format="{{.ID}}")
}

# Stop and remove all exited container that use the `consensus-specs:$version` image
cleanup() {
  echo "Stop and remove non running containers."
  docker rm $(docker stop $(get_container_name))
}

# Copy the coverage report from the container to the local
copy_coverage_report() {
  docker cp $(get_container_name):$WORKDIR/$COV_HTML_OUT ./$COV_HTML_OUT
}

# Equivalent to `make test`
docker run -w $WORKDIR consensus-specs:$version \
    pytest -n $number_of_core --disable-bls $coverage_scope --cov-report="html:${COV_HTML_OUT}" --cov-branch eth2spec

# Get coverage report form container instance
$(copy_coverage_report)

# Stop and remove all containers that use the `consensus-specs:$version` image when exiting
#  the script. It helps user to limit container instances.
trap cleanup EXIT

$SHELL