# Rename the build stage from 'base' to 'builder' for clarification and code readability
FROM python:3.12.4-slim-bullseye as builder

ENV DEBIAN_FRONTEND=noninteractive \
    WORKDIR=/consensus-specs  \
    PIP_UPGRADE_CMD="python -m pip install --upgrade pip" \
    INSTALL_CMD="apt install -y git build-essential"

RUN mkdir ${WORKDIR}
WORKDIR ${WORKDIR}

# Chain the commands together
RUN apt update && ${INSTALL_CMD} && ${PIP_UPGRADE_CMD} && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the builder
COPY . .

# Inline installation commands
RUN make pyspec
