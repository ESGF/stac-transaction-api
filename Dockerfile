FROM python:3.12-slim AS cert

ARG CERT_CN=localhost
ARG CERT_O=esgf-west.org

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

# Generate self-signed cert
RUN mkdir -p /etc/ssl/transaction \
    && openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout /etc/ssl/transaction/server.key \
        -out /etc/ssl/transaction/server.crt \
        -subj "/O=${CERT_O}/OU=discovery-api/CN=${CERT_CN}"


FROM python:3.12-slim AS builder

# Dependency group providing the authorizer: globus (default) or ceda
ARG AUTHORIZER_GROUP=globus

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /var/task

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main,${AUTHORIZER_GROUP}


# Shared by local and production: venv + app code, with nginx (TLS on 8000,
# 2 MiB request limit) in front of uvicorn (plain HTTP on 127.0.0.1:8001, not
# reachable from outside the container), both in one container.
FROM python:3.12-slim AS runtime

ENV PATH="/var/task/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /var/task

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

COPY --from=builder /var/task/.venv ./.venv
COPY ./src .
# Read at runtime for the API version
COPY pyproject.toml .
COPY --from=cert /etc/ssl/transaction /etc/ssl/transaction
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/start.sh /start.sh

EXPOSE 8000

ENTRYPOINT ["/start.sh"]


# --forwarded-allow-ips: proxies whose X-Forwarded-For entries uvicorn trusts
# when logging the client address: nginx (loopback) and the ALB (private ranges)

# docker build --target local .
FROM runtime AS local

# uvicorn is also reachable directly on 8001, bypassing nginx (dev only)
CMD ["uvicorn", "api:app", \
     "--host", "0.0.0.0", "--port", "8001", \
     "--forwarded-allow-ips", "127.0.0.1", \
     "--reload"]

EXPOSE 8001


# Default target (last stage): docker build .
FROM runtime AS production

# Reachable only through nginx
CMD ["uvicorn", "api:app", \
     "--host", "127.0.0.1", "--port", "8001", \
     "--forwarded-allow-ips", "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"]
