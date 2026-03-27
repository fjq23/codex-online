FROM ubuntu:24.04

ARG CODEX_VERSION=0.116.0
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG ALL_PROXY
ARG NO_PROXY
ENV DEBIAN_FRONTEND=noninteractive
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    ALL_PROXY=${ALL_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    all_proxy=${ALL_PROXY} \
    no_proxy=${NO_PROXY}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    dnsutils \
    git \
    gosu \
    inetutils-telnet \
    iproute2 \
    iputils-ping \
    jq \
    less \
    nano \
    net-tools \
    nodejs \
    npm \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    ripgrep \
    traceroute \
    tini \
    tmux \
    ttyd \
    unzip \
    vim-tiny \
    wget \
    zip \
  && npm install -g "@openai/codex@${CODEX_VERSION}" \
  && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash codex

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY bashrc /home/codex/.bashrc
COPY tmux.conf /home/codex/.tmux.conf

RUN chmod 0755 /usr/local/bin/entrypoint.sh \
  && chown codex:codex /home/codex/.bashrc /home/codex/.tmux.conf

ENV HOME=/home/codex \
    CODEX_HOME=/codex-home \
    WORKSPACE_DIR=/workspace \
    TMUX_SESSION_PREFIX=ws \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /workspace

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
