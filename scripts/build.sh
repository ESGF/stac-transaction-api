#!/bin/bash

SCRIPT_DIR=$(dirname "$(realpath "$0")")
cd "$SCRIPT_DIR" || exit

IMAGE=stac_transaction_api

SRC_DIR=src
BUILD_DIR=build
ZIP_FILE=lambda.zip

docker build --build-arg USER_ID=$(id -u) --build-arg GROUP_ID=$(id -g) -t $IMAGE .

cd ..
if [ -e $BUILD_DIR ]; then
    rm -r $BUILD_DIR
fi
mkdir $BUILD_DIR
cp requirements.txt $BUILD_DIR
cp $SRC_DIR/*.py $BUILD_DIR

docker run -it --rm -v $(pwd)/$BUILD_DIR:/var/task $IMAGE /bin/bash -c "
    cd /var/task && \
    pip install -r requirements.txt -t . && \
    zip -r9 $ZIP_FILE ."
