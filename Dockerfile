# FROM public.ecr.aws/sam/build-python3.10:latest
FROM public.ecr.aws/lambda/python:3.9

ENV PATH="/root/.local/bin:/sbin:/usr/sbin:${PATH}"
ENV LD_LIBRARY_PATH=/lib:/usr/lib:/usr/local/lib

RUN curl -sSL https://install.python-poetry.org | python3 -
RUN yum update -y
RUN yum groupinstall -y "Development Tools"
RUN yum install -y gcc git libcurl-devel libssl-dev make openssl-devel which
RUN git clone https://github.com/confluentinc/librdkafka  && \
    cd librdkafka && git checkout tags/v2.6.0 && \
    ./configure --install-deps && make && make install && \
    ldconfig

COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# COPY poetry.lock ${LAMBDA_TASK_ROOT}
# COPY pyproject.toml ${LAMBDA_TASK_ROOT}
# RUN poetry config virtualenvs.create false && \
#     poetry install --no-interaction --no-ansi

COPY ./src ${LAMBDA_TASK_ROOT}

# RUN cd /var/lang/lib/python3.10/site-packages && \
#     zip -r9 /var/task/lambda.zip . && \
#     cd /var/task/src && \
#     zip -r9 /var/task/lambda.zip .

CMD ["api.handler"]