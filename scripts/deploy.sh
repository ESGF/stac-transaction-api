#!/bin/bash

AWS_PROFILE='esgf2'
ZIP_FILE='lambda.zip'

function update_lambda_function {
    lambda_function=$1
    aws --profile ${AWS_PROFILE} lambda update-function-code \
        --function-name ${lambda_function} \
        --zip-file fileb://${ZIP_FILE} \
        --no-cli-pager
}

function publish_version {
    lambda_function=$1
    aws --profile ${AWS_PROFILE} lambda publish-version \
        --function-name ${lambda_function} \
        --no-cli-pager
}

function update_configuration {
    aws --profile ${AWS_PROFILE} lambda update-function-configuration \
        --function-name ${lambda_function} \
        --environment Variables="{BUCKET=${BUCKET},\
                                  ENVIRONMENT=${ENVIRONMENT}}"
}

if [ $# -lt 2 ]; then
    echo 'Usage:'
    echo '    deploy.sh {upodate_code|publish_version} {api|authorizer} [dev]'
    exit 1
fi

case $1 in
    update_code)
        lambda_function=$2
        ./scripts/build.sh
        update_lambda_function ${lambda_function}
        ;;
    publish_version)
        lambda_function=$2
        publish_version ${lambda_function}
        ;;
    *)
        echo 'Unrecognized lambda function'
        ;;
esac
