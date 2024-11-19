FROM python:3.9

ENV LD_LIBRARY_PATH=/lib:/usr/lib:/usr/local/lib
ENV PATH=/root/.local/bin:/sbin:/usr/sbin:${PATH}

RUN apt-get update
RUN apt-get install build-essential gcc git make which -y
RUN git clone https://github.com/confluentinc/librdkafka  && \
    cd librdkafka && git checkout tags/v2.6.0 && \
    ./configure --install-deps && make && make install && \
    ldconfig

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./src .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]