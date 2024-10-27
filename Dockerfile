FROM public.ecr.aws/sam/build-python3.10:latest-x86_64

ENV PATH="/root/.local/bin:/sbin:/usr/sbin:${PATH}"

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN rpm --import https://packages.confluent.io/rpm/7.0/archive.key && \
    echo '[Confluent-Clients]' > /etc/yum.repos.d/confluent.repo && \
    echo 'name=Confluent Clients repository' >> /etc/yum.repos.d/confluent.repo && \
    echo 'baseurl=https://packages.confluent.io/clients/rpm/centos/7/x86_64' >> /etc/yum.repos.d/confluent.repo && \
    echo 'gpgcheck=1' >> /etc/yum.repos.d/confluent.repo && \
    echo 'gpgkey=https://packages.confluent.io/clients/rpm/archive.key' >> /etc/yum.repos.d/confluent.repo && \
    echo 'enabled=1' >> /etc/yum.repos.d/confluent.repo && \
    rpm --import https://packages.confluent.io/rpm/7.0/archive.key && \
    yum install -y librdkafka-devel && \
    pip install --upgrade pip

WORKDIR /var/task
COPY . .

RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi && \
    cd /var/lang/lib/python3.10/site-packages && \
    zip -r9 /var/task/lambda.zip . && \
    cd /var/task/src && \
    zip -r9 /var/task/lambda.zip .
