# Build the consensus-specs image using the builder pattern.
# This image is base on the Debian slim distribution.
FROM python:3.11.0-slim-bullseye as base


FROM base as builder
RUN mkdir /consensus-specs
WORKDIR /consensus-specs
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y git
RUN python -m pip install --upgrade pip

COPY . .

RUN pip install -r requirements_preinstallation.txt -e .[lint] -e .[test]
RUN python setup.py pyspecdev
