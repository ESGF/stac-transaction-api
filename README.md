# New Document

# STAC Transaction API


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
