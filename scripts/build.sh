#!/bin/bash

# You'll need a profile (esgf2) managed by vault for account 730335463484

IMAGE=stac-transaction-api

aws ecr get-login-password \
    --profile esgf2 \
    --region us-east-1 | docker login --username AWS --password-stdin 730335463484.dkr.ecr.us-east-1.amazonaws.com

docker build --platform=linux/x86_64 -f ../Dockerfile -t $IMAGE:latest ..

docker tag $IMAGE:latest 730335463484.dkr.ecr.us-east-1.amazonaws.com/$IMAGE:latest

docker push 730335463484.dkr.ecr.us-east-1.amazonaws.com/$IMAGE:latest