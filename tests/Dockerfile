FROM debian:stable-20230904-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /work
ENV PYENV_ROOT=/work/.pyenv
ENV PATH=${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:$PATH
COPY .python-version /work

RUN \
  apt-get update \
  && apt-get install -y --no-install-recommends \
      apt-transport-https \
      build-essential \
      ca-certificates \
      clang-format \
      curl \
      gnupg \
      git \
      zlib1g-dev \
      libffi-dev \
      liblzma-dev \
      libreadline-dev \
      libssh-dev \
      libssl-dev \
      libsqlite3-dev \
  && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch v2.3.21 https://github.com/pyenv/pyenv "${PYENV_ROOT}" \
  && cd /work \
  && pyenv local | xargs -L 1 pyenv install \
  && cd -
CMD ["/bin/bash"]
