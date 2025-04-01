# STAC Transaction API

### Running Locally
Prerequisites
- [Docker](https://www.docker.com/) installed
- `CLIENT_ID` and `CLIENT_SECRET` created from [Globus Developers Setting](https://app.globus.org/settings/developers)

Getting up and running
- Create a `.env` file under `src/settings`
-- Add the `CLIENT_ID` and `CLIENT_SECRET` and set `RUN_ENVIRONMENT=local` in the `.env` file
- To build the local Confluent kafka environment as well as the transaction API, run `docker compose -f compose-kafka.yaml up` This can take a minute or two to complete.
- To build the FastAPI and esgvoc container, run
    ```
    docker volume create esgvoc
    
    docker build -f ./Dockerfile-esgvoc -t esgvoc .
    docker run --name esgvoc \
      --detach \
      -v esgvoc:/root/.local/share/esgvoc \
      -it esgvoc

    docker build -t stac-transaction-fastapi .
    docker run --name stac-transaction-fastapi \
      --detach \
      -v esgvoc:/root/.local/share/esgvoc \
      -v ./src:/var/task \
      -p 8000:8000 \
      -it stac-transaction-api
    ```
- For ECS deployments, there are basic scripts in the scripts directory for building and deploying

## To-do
- Basic instructions for deployment to AWS ECS
- Add Consumer support
- Add Discovery support

# DEPRECATED
### Amazon API Gateway (API with Authorizer)

Authorizer:
 - Lambda function: authorizer
 - Lambda event payload: Token
 - Token source: Authorization
 - Token validation: Bearer\s[0-9A-Za-z]+
 - Authorization caching: 300 seconds

API:
```
/
  /{proxy+}
    POST
    PUT
    DELETE
```
with stages:
 - dev
 - stage
 - prod
and stage variable `lambdaAlias` set for each stage to `dev`, `stage`, `prod`, respectively.

### Amazon Lambda

The two functions share the same deployment zip file (`lambda.zip`):
 - `authorizer`
   - Runtime: Python 3.10
   - Handler: `authorizer.authorizer`
 - `api`
   - Runtime: Python 3.10
   - Handler: `api.api`
Different versions of the `api` Lambda function have assigned aliases `dev`, `stage`, `prod`.
API Gateway reads the `lambdaAlias` variable uses its value as an alias, `api:${stageVariables.lambdaAlias}` to call a corresponding version of the `api` Lambda function.

Build the deployment zip file:
```
./scripts/build.sh
```

Update Lambda function code:
```
./scripts/deploy.sh {update_code|publish_version} {api|authorizer} [dev]
```
