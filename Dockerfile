FROM public.ecr.aws/sam/build-python3.9:latest-x86_64

ENV LD_LIBRARY_PATH=/lib:/usr/lib:/usr/local/lib
ENV PATH=/root/.local/bin:/sbin:/usr/sbin:${PATH}

RUN yum update -y
RUN yum groupinstall -y "Development Tools"
RUN yum install -y gcc git libcurl-devel libssl-dev make openssl-devel which
RUN git clone https://github.com/confluentinc/librdkafka  && \
    cd librdkafka && git checkout tags/v2.6.0 && \
    ./configure --install-deps && make && make install && \
    ldconfig

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./src .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]