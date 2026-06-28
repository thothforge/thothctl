FROM mcr.microsoft.com/devcontainers/python:3.12

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    graphviz \
    libgraph-easy-perl \
    wkhtmltopdf \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*
