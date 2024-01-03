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
FORK_TO_TEST=phase0
NUMBER_OF_CORES=4
WORKDIR="//consensus-specs//tests//core//pyspec"
ETH2SPEC_FOLDER_NAME="eth2spec"
CONTAINER_NAME="consensus-specs-tests"
DATE=$(date +"%Y%m%d-%H-%M")
# Default flag values
version=$(git log --pretty=format:'%h' -n 1)
number_of_core=4

# initialize a test result directory
mkdir -p ./testResults

display_help() {
  echo "Run 'consensus-specs' tests from a container instance."
  echo "Be sure to launch Docker before running this script."
  echo
  echo "Syntax: build_run_test.sh [--v TAG | --n NUMBER_OF_CORE | --f FORK_TO_TEST | --p PRESET_TYPE | --a | --h HELP]"
    echo "  --f <fork>   Specify the fork to test"
    echo "  --v <version> Specify the version"
    echo "  --n <number> Specify the number of cores"
    echo "  --p <type>   Specify the test preset type"
    echo "  --a          Test all forks"
    echo "  --cleanup    Stop and remove the 'consensus-specs-tests' container"
    echo "  --h          Display this help and exit"
}

# Stop and remove the 'consensus-specs-dockerfile-test' container.
# If this container doesn't exist, then a error message is printed
#  (but the process is not stopped).
cleanup() {
  echo "Stop and remove the 'consensus-specs-tests' container."
  docker stop $CONTAINER_NAME || true && docker rm $CONTAINER_NAME || true

}


# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --f) FORK_TO_TEST="$2"; shift ;;
        --v) version="$2"; shift ;;
        --n) NUMBER_OF_CORES="$2"; shift ;;
        --p) TEST_PRESET_TYPE="$2"; shift ;;
        --a) FORK_TO_TEST="all" ;;
        --h) display_help; exit 0 ;;
        --cleanup) cleanup; exit 0 ;;
        *) echo "Unknown parameter: $1"; display_help; exit 1 ;;
    esac
    shift
done


# Only clean container after user exit console
trap cleanup SIGINT

# Copy the results from the container to local
copy_test_results() {
  local fork_name="$1"  # Storing the first argument in a variable
  echo $fork_name

  docker cp $CONTAINER_NAME:$WORKDIR/test-reports/test_results.xml ./testResults/test-results-$fork_name-$DATE.xml
}

# Equivalent to `make test`
docker build ../ -t consensus-specs:$version -f ../docker/Dockerfile
if [ "$FORK_TO_TEST" == "all" ]; then
  for fork in "${ALL_EXECUTABLE_SPECS[@]}"; do
    docker run --name $CONTAINER_NAME consensus-specs:$version \
      make citest fork=$fork TEST_PRESET_TYPE=$TEST_PRESET_TYPE NUMBER_OF_CORES=$NUMBER_OF_CORES
      copy_test_results $fork
  done
else
  docker run --name $CONTAINER_NAME consensus-specs:$version \
      make citest fork=$FORK_TO_TEST TEST_PRESET_TYPE=$TEST_PRESET_TYPE NUMBER_OF_CORES=$NUMBER_OF_CORES
  copy_test_results $FORK_TO_TEST
fi


cleanup