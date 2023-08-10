# Build the consensus-specs image using the builder pattern.
# This image is based on the Debian slim distribution.
FROM python:3.11.0-slim-bullseye as base

# Create the working directory
RUN mkdir /consensus-specs
WORKDIR /consensus-specs

# Set a non-interactive environment to suppress prompts
ENV DEBIAN_FRONTEND=noninteractive

# Update packages, install git, upgrade pip, and clean up unnecessary files
RUN apt update && \
    apt install -y git && \
    python -m pip install --upgrade pip && \
    rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container
COPY . .

# Install requirements and setup
RUN pip install -r requirements_preinstallation.txt -e .[lint] -e .[test] && \
    python setup.py pyspecdev
