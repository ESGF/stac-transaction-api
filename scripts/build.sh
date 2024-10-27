#!/bin/bash

IMAGE=stac_transaction_api
ZIP_FILE=lambda.zip

docker build -t $IMAGE .
docker create --name temp_container $IMAGE
docker cp temp_container:/var/task/$ZIP_FILE .
docker rm temp_container
