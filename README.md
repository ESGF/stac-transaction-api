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
  - Builds the `local` target of the `Dockerfile`: plain HTTP on `http://localhost:8000`, with `--reload` against `./src`
  - Or without compose:
    ```
    docker build --target local -t stac-transaction-api:local .
    docker run --rm -p 8000:8000 \
      --env-file ./src/settings/.env \
      -v ./src:/var/task -v /var/task/.venv \
      stac-transaction-api:local
    ```

## To-do
- Add Consumer support
- Add Discovery support
