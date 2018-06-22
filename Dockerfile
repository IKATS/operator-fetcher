FROM ubuntu:16.04

LABEL license="Apache License, Version 2.0"
LABEL copyright="CS Systèmes d'Information"
LABEL maintainer="contact@ikats.org"
LABEL version="0.8.0"

# Install dependencies
RUN apt-get update \
 && apt-get install -y \
    git \
    python3 \
    python3-git \
    python3-yaml \
 && rm -rf /var/lib/apt/lists/*

# Adding assets
RUN mkdir -p /app/op /app/fetch-op /app/local
ADD assets/main.py /app/
ADD assets/catalog.py /app/
ADD assets/repo-list.yml /app/

VOLUME /app/op
VOLUME /app/local

# Do git clone no matter the validity of the certificate
ENV GIT_SSL_NO_VERIFY true

# Starting component
WORKDIR /app
CMD python3 ./main.py
