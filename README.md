# STAC Transaction API

### Running Locally
Prerequisites
- [Docker](https://www.docker.com/) installed
- `CLIENT_ID` and `CLIENT_SECRET` created from [Globus Developers Setting](https://app.globus.org/settings/developers)

Getting up and running
- Create a `.env` file under `src/settings`
  - For an example, please see `src/settings/example.env`
  - Add the `CLIENT_ID` and `CLIENT_SECRET` and set `RUN_ENVIRONMENT=local` in the `.env` file
- To build the local Confluent kafka environment, run `docker compose -f compose-kafka.yaml up` This can take a minute or two to complete.
- To run the FastAPI container locally, run `docker compose up --build`
  - Builds the `local` target of the `Dockerfile`: HTTPS on `https://localhost:8000` (self-signed cert, nginx in front of uvicorn), with `--reload` against `./src`; uvicorn is also published directly on `http://localhost:8001`, bypassing nginx (no TLS, no 2 MiB limit)
  - Or without compose:
    ```
    docker build --target local -t stac-transaction-api:local .
    docker run --rm -p 8000:8000 -p 8001:8001 \
      --env-file ./src/settings/.env \
      -v ./src:/var/task -v /var/task/.venv \
      -v ./pyproject.toml:/var/task/pyproject.toml:ro \
      stac-transaction-api:local
    ```

### Production-like (nginx + TLS)
- `docker compose --profile production up --build production` serves `https://localhost:8000` (self-signed cert)
- The `production` target runs nginx and uvicorn in one container (see `nginx/start.sh`). nginx terminates TLS on 8000 and rejects request bodies over 2 MiB (HTTP 413); uvicorn listens only on `127.0.0.1:8001` inside the container
- Mount a real cert/key at `/etc/ssl/transaction/server.{crt,key}` to replace the self-signed one

## To-do
- Add Consumer support
- Add Discovery support
