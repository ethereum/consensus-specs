#! /bin/sh

# Run flake8 to test the image consensus-specs:<TAG>
# This script must only be used to check the consensus-specs:<TAG>
#  consistency.

# Constants
LINTER_CONFIG_FILE=".//linter.ini"
CONTAINER_NAME="consensus-specs-dockerfile-test"

# Default flag values
version=latest

# Parse provided flags
while getopts v: flag
do
    case "${flag}" in
        v) version=${OPTARG};;
        \?) echo "not valid -$OPTARG:${OPTARG}";;
    esac
done

# Stop and remove the 'consensus-specs-dockerfile-test' container.
# If this container doesn't exist, then a error message is printed
#  (but the process is not stopped).
cleanup() {
  echo "Stop and remove the 'consensus-specs-dockerfile-test' container."
  docker stop $CONTAINER_NAME || true && docker rm $CONTAINER_NAME || true
}

cleanup
docker run --name $CONTAINER_NAME consensus-specs:$version \
  flake8 --config $LINTER_CONFIG_FILE . # maybe too slow if parse all .py files ?
cleanup
