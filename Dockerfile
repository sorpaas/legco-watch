FROM debian:7.7

RUN apt-get update && apt-get -y install build-essential \
 python-dev \
 python-setuptools \
 python-psycopg2 \
 python-pip \
 libpq-dev \
 vim \
 tmux \
 htop \
 git \
 libffi-dev \
 libxml2-dev \
 libxslt1-dev \
 curl \
 abiword

ENV PROJECT_PATH /legcowatch
ENV INSIDE_DOCKER TRUE

WORKDIR ${PROJECT_PATH}
ADD requirements ${PROJECT_PATH}/requirements
RUN pip install -r requirements/base_reqs.txt
RUN pip install -r requirements/celery_reqs.txt

ADD . ${PROJECT_PATH}

WORKDIR ${PROJECT_PATH}/app

# Runs syncdb, migrate, collectstatic, then starts the uwsgi server
CMD ["../bin/appserver.sh"]

EXPOSE 8001
