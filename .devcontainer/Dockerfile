# Use Python 3.11 with conda for package management
FROM continuumio/miniconda3:latest

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    vim \
    nano \
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    # Redis CLI for debugging
    redis-tools \
    # Network tools
    netcat-openbsd \
    telnet \
    # Process monitoring
    htop \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create conda environment with Python 3.11
RUN conda create -n yokedcache python=3.11 -y
SHELL ["conda", "run", "-n", "yokedcache", "/bin/bash", "-c"]

# Update conda and install base packages
RUN conda update -n base -c defaults conda -y && \
    conda install -n yokedcache -c conda-forge \
    pip \
    setuptools \
    wheel \
    -y

# Set the conda environment as default
ENV PATH /opt/conda/envs/yokedcache/bin:$PATH
ENV CONDA_DEFAULT_ENV yokedcache

# Create workspace directory
WORKDIR /workspace

# Copy requirements first to leverage Docker caching
COPY requirements-dev.txt requirements-full.txt pyproject.toml ./

# Install Python dependencies
RUN conda run -n yokedcache pip install --no-cache-dir -r requirements-dev.txt && \
    conda run -n yokedcache pip install --no-cache-dir -r requirements-full.txt

# Install additional development tools
RUN conda run -n yokedcache pip install --no-cache-dir \
    ipython \
    jupyter \
    jupyterlab \
    pre-commit \
    bandit \
    safety \
    rich \
    typer

# Configure Git (will be overridden by mounted config)
RUN git config --global user.name "Developer" && \
    git config --global user.email "dev@yokedcache.local" && \
    git config --global init.defaultBranch main

# Set up shell
RUN echo "source activate yokedcache" >> ~/.bashrc
RUN echo "cd /workspace" >> ~/.bashrc

# Expose common ports
EXPOSE 58000 58080 58888

# Set default command
CMD ["/bin/bash"]
