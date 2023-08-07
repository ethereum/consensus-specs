FROM python:3.11.0-slim-bullseye as base

RUN mkdir /consensus-specs
WORKDIR /consensus-specs

FROM base as builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y git
RUN python -m pip install --upgrade pip

COPY . .

RUN pip install -r requirements-dev.txt -r requirements_preinstallation.txt
RUN python setup.py pyspecdev
