# New Document

# STAC Ingest API


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
  /v0.1
    /{proxy+}
       POST
```
with stages:
 - dev
 - stage
 - prod


### Amazon Lambda

The two functions share the same deployment zip file (`lambda.zip`):
 - `authorizer`
   - Runtime: Python 3.10
   - Handler: `ingest.authorizer`
 - `api`
   - Runtime: Python 3.10
   - Handler: `ingest.api`

Build the deployment zip file:
```
./scripts/build.sh
```

Update Lambda function code:
```
./scripts/deploy.sh {authorizer|api} {dev|prod}
```
