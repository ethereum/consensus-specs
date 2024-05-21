## Docker related information

This dockerfile sets up the dependencies required to run consensus-spec tests. The docker image can be locally built with:
- `docker build ./ -t $IMAGE_NAME -f ./docker/Dockerfile`


Handy commands:
- `docker run -it $IMAGE_NAME /bin/sh` will give you a shell inside the docker container to manually run any tests
- `docker run  $IMAGE_NAME make citest` will run the make citest command inside the docker container

Ideally manual running of docker containers is for advanced users, we recommend the script based approach described below for most users.

The `scripts/build_run_docker_tests.sh` script will cover most usecases. The script allows the user to configure the fork(altair/bellatrix/capella..), `$IMAGE_NAME` (specifies the container to use), number of cores, preset type (mainnet/minimal), and test all forks flags. Ideally, this is the main way that users interact with the spec tests instead of running it locally with varying versions of dependencies.

E.g:
- `./build_run_test.sh --p mainnet --n 16` will run the mainnet preset tests with 16 threads
- `./build_run_test.sh --a` will run all the tests across all the forks
- `./build_run_test.sh --f deneb --n 16` will only run deneb tests on 16 threads

Results are always placed in a folder called `./testResults`. The results are `.xml` files and contain the fork they represent and the date/time they were run at.