FROM python:3.12-slim AS cert

ARG CERT_CN=uvicorn
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


# Shared by local and production: venv + app code, no TLS, no CMD
FROM python:3.12-slim AS runtime

ENV PATH="/var/task/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /var/task

COPY --from=builder /var/task/.venv ./.venv
COPY ./src .

EXPOSE 8000


# docker build --target local .
FROM runtime AS local

CMD ["uvicorn", "api:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--reload"]


# Default target (last stage): docker build .
FROM runtime AS production

COPY --from=cert /etc/ssl/transaction /etc/ssl/transaction

CMD ["uvicorn", "api:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--forwarded-allow-ips", "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16", \
     "--ssl-keyfile", "/etc/ssl/transaction/server.key", \
     "--ssl-certfile", "/etc/ssl/transaction/server.crt"]
