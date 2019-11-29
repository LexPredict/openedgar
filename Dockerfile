# CC Specific Dockerfile implementing steps at https://github.com/LexPredict/openedgar/blob/master/INSTALL.md
# Allows the use of OpenEDGAR in AKS
FROM ubuntu:18.04
MAINTAINER Michael Seddon (michael.seddon@cliffordchance.com)

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Package installation
RUN apt update
RUN apt upgrade -y
RUN apt install -y software-properties-common build-essential python3-dev python3-pip virtualenv git-all
# to be removed when rabbit is in its own container
RUN apt install -y rabbitmq-server
RUN apt-get install -y openjdk-8-jdk

# Clone OpenEDGAR repository
WORKDIR /opt
RUN mkdir /opt/openedgar

# Set up Python venv
WORKDIR /opt/openedgar/
RUN virtualenv -p /usr/bin/python3 env
COPY lexpredict_openedgar/requirements/full.txt lexpredict_openedgar/requirements/full.txt
RUN ./env/bin/pip install -r lexpredict_openedgar/requirements/full.txt
RUN ./env/bin/pip install azure-mgmt-resource azure-mgmt-datalake-store azure-datalake-store azure-storage-blob
COPY tika/tika-server-1.21.jar /opt/openedgar/tika/tika-server-1.21.jar
COPY lexpredict_openedgar/ /opt/openedgar/lexpredict_openedgar/

COPY docker/default.env /opt/openedgar/
RUN cp lexpredict_openedgar/sample.env lexpredict_openedgar/.env
#COPY docker/erlang-solutions_1.0_all.deb lexpredict_openedgar/erlang-solutions_1.0_all.deb
COPY docker/oe-entrypoint.sh /usr/local/bin/
COPY docker/run_edgar.py /opt/openedgar/lexpredict_openedgar/run_edgar.py
COPY docker/dot_env.sh /opt/openedgar
RUN mkdir /data

ENTRYPOINT ["oe-entrypoint.sh"]