#!/bin/bash

# Make sure to build the containers first
# If you do not want to run in `--detach mode`, then you'll need
# to remove the `--detach` flag and run the below commands in 
# separate terminal tabs/windows

docker run \
    --detach \
    -p 8000:8000 \
    -it stac-transaction-api
