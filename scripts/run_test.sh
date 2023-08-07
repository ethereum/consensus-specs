# /bin/sh

# constants
ALL_EXECUTABLE_SPECS=("phase0" "altair" "bellatrix" "capella" "deneb" "eip6110" "whisk")
TEST_PRESET_TYPE=minimal
WORKDIR="//consensus-specs//tests//core//pyspec"

COV_HTML_OUT=.htmlcov

# default flag value
version=latest
number_of_core=4

# generate coverage scope
name="eth2spec"
coverage_scope=()
for spec in "${ALL_EXECUTABLE_SPECS[@]}"
do
    coverage_scope+=("--cov=${name}.${spec}.${TEST_PRESET_TYPE}")
done

# Parse flags
while getopts v:n: flag
do
    case "${flag}" in
        v) version=${OPTARG};;
        n) number_of_core=${OPTARG};;
        \?) echo "not valid -$OPTARG:${OPTARG}";;
    esac
done

# Get IDs of container that run the image `consensus-specs:$version` and are exited.
get_container_name() {
  echo $(docker ps -a -q --filter ancestor="consensus-specs:$version" --filter status="exited" --format="{{.ID}}")
}

# Stop and remove all container that use the `consensus-specs:$version` image
cleanup() {
  echo "Stop and remove current container"
  docker rm $(docker stop $(get_container_name))
}

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

# for testing purpose
$SHELL