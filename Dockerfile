FROM ubuntu:18.04

LABEL license="Apache License, Version 2.0"
LABEL copyright="CS Systèmes d'Information"
LABEL maintainer="contact@ikats.org"
LABEL version="0.12.0"

# Install dependencies
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  git \
  rsync \
  python3 \
  python3-yaml \
  python3-pip \
  python3-dev \
  build-essential && \
  pip3 install psycopg2-binary && \
  mkdir -p /app/op /app/fetch-op /app/local /app/fam && \
  rm -rf /var/lib/apt/lists/*

# Adding assets
COPY assets/* /app/

VOLUME /app/op
VOLUME /app/local
VOLUME /app/fam

# Do git clone no matter the validity of the certificate
ENV GIT_SSL_NO_VERIFY true

# Number of seconds the app will wait until considering the repository not reachable
ENV CONNECTION_TIMEOUT 5

# Starting component
WORKDIR /app
CMD python3 ./entry_point.py
