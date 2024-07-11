#!/bin/bash

AWS_PROFILE='esgf2'
ZIP_FILE='lambda.zip'

function update_lambda_function {
    lambda_function=$1
    aws --profile ${AWS_PROFILE} lambda update-function-code \
        --function-name ${lambda_function} \
        --zip-file fileb://build/${ZIP_FILE}
}

function update_configuration {
    aws --profile ${AWS_PROFILE} lambda update-function-configuration \
        --function-name ${lambda_function} \
        --environment Variables="{BUCKET=${BUCKET},\
                                  ENVIRONMENT=${ENVIRONMENT}}"
}

if [ $# -ne 2 ]; then
    echo 'Usage:'
    echo '    deploy.sh {authorizer|api {prod|dev}'
    exit 1
fi

case $1 in
    api)
        lambda_function='api'
        ./scripts/build.sh
        update_lambda_function ${lambda_function}
        #sleep 5
        #update_configuration ${lambda_function}
        ;;
    authorizer)
        lambda_function='authorizer'
        ./scripts/build.sh
        update_lambda_function ${lambda_function}
        #sleep 5
        #update_configuration ${lambda_function}
        ;;
    *)
        echo 'Unrecognized lambda function'
        ;;
esac
