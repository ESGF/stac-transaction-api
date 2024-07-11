#!/bin/bash

SRC_DIR='src/'
BUILD_DIR='build/'
ZIP_FILE='lambda.zip'

IMAGE='public.ecr.aws/sam/build-python3.10:latest-x86_64'
USER_ID=$(id -u)
GROUP_ID=$(id -g)

if [ -e $BUILD_DIR ]; then
    rm -r $BUILD_DIR
fi
mkdir -p $BUILD_DIR
cp requirements.txt $BUILD_DIR
cp $SRC_DIR/*.py $BUILD_DIR

docker pull $IMAGE
docker run -it --rm -v $(pwd)/$BUILD_DIR:/var/task --user $USER_ID:$GROUP_ID $IMAGE \
    /bin/bash -c "cd /var/task && \
                  pip install --no-deps -r requirements.txt -t . && \
                  zip -r9 $ZIP_FILE ."
