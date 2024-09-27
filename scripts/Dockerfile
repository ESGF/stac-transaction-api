FROM public.ecr.aws/sam/build-python3.10:latest-x86_64

ENV PATH="/sbin:/usr/sbin:${PATH}"

COPY confluent.repo /etc/yum.repos.d/confluent.repo
RUN rpm --import https://packages.confluent.io/rpm/7.0/archive.key && \
    yum install -y librdkafka-devel && \
    pip install --upgrade pip

ARG USER_ID
ARG GROUP_ID
RUN groupadd -g $GROUP_ID mygroup && \
    useradd -m -u $USER_ID -g $GROUP_ID myuser

USER myuser
WORKDIR /var/task
