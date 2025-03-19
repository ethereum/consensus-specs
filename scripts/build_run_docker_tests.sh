#! /bin/bash

# Run 'consensus-specs' tests from a docker container instance.
# *Be sure to launch Docker before running this script.*
#
# It does the below:
#   1. Run pytest for consensus-specs in a container.
#   2. Copy and paste the coverage report.
#   3. Remove all exited containers that use the consensus-specs:<TAG> images.


# Set variables
ALL_EXECUTABLE_SPECS=("phase0" "altair" "bellatrix" "capella" "deneb" "electra" "fulu" "eip7441")
TEST_PRESET_TYPE=minimal
FORK_TO_TEST=phase0
WORKDIR="//consensus-specs//tests//core//pyspec"
ETH2SPEC_FOLDER_NAME="eth2spec"
CONTAINER_NAME="consensus-specs-tests"
DATE=$(date +"%Y%m%d-%H-%M")
# Default flag values
version=$(git log --pretty=format:'%h' -n 1)
IMAGE_NAME="consensus-specs:$version"

# displays the available options
display_help() {
  echo "Run 'consensus-specs' tests from a container instance."
  echo "Be sure to launch Docker before running this script."
  echo
  echo "Syntax: build_run_test.sh [--v TAG | --f FORK_TO_TEST | --p PRESET_TYPE | --a | --h HELP]"
    echo "  --f <fork>   Specify the fork to test"
    echo "  --i <image_name> Specify the docker image to use"
    echo "  --p <type>   Specify the test preset type"
    echo "  --a          Test all forks"
    echo "  --h          Display this help and exit"
}

# Stop and remove the 'consensus-specs-dockerfile-test' container.
# If this container doesn't exist, then a error message is printed
#  (but the process is not stopped).
cleanup() {
  echo "Stop and remove the 'consensus-specs-tests' container."
  docker stop $CONTAINER_NAME || true && docker rm $CONTAINER_NAME || true

}

# Copy the results from the container to a local folder
copy_test_results() {
  local fork_name="$1"  # Storing the first argument in a variable

  docker cp $CONTAINER_NAME:$WORKDIR/test-reports/test_results.xml ./testResults/test-results-$fork_name-$DATE.xml
}

# Function to check if the Docker image already exists
image_exists() {
    docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "$1"
}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --f) FORK_TO_TEST="$2"; shift ;;
        --v) IMAGE_NAME="$2"; shift ;;
        --p) TEST_PRESET_TYPE="$2"; shift ;;
        --a) FORK_TO_TEST="all" ;;
        --h) display_help; exit 0 ;;
        *) echo "Unknown parameter: $1"; display_help; exit 1 ;;
    esac
    shift
done

# initialize a test result directory
mkdir -p ./testResults

# Only clean container after user exit console
trap cleanup SIGINT

# Build Docker container if it doesn't exist
if ! image_exists "$IMAGE_NAME"; then
    echo "Image $IMAGE_NAME does not exist. Building Docker image..."
    docker build ../ -t $IMAGE_NAME -f ../docker/Dockerfile
else
    echo "Image $IMAGE_NAME already exists. Skipping build..."
fi

# Equivalent to `make test with the subsequent flags`
if [ "$FORK_TO_TEST" == "all" ]; then
  for fork in "${ALL_EXECUTABLE_SPECS[@]}"; do
    docker run --name $CONTAINER_NAME $IMAGE_NAME \
      make test fork=$fork preset=$TEST_PRESET_TYPE
      copy_test_results $fork
  done
else
  docker run --name $CONTAINER_NAME $IMAGE_NAME \
      make test fork=$FORK_TO_TEST preset=$TEST_PRESET_TYPE
  copy_test_results $FORK_TO_TEST
fi

# Stop and remove the container
cleanup
