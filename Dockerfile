FROM python:3.6

RUN apt-get update && apt-get install -y postgresql-client-common libpq-dev

RUN pip install --upgrade pip

ENV OPENEDGAR_DIR /opt/openedgar/lexpredict_openedgar
RUN mkdir -p ${OPENEDGAR_DIR}
WORKDIR ${OPENEDGAR_DIR}

# might be necessary for pandas=0.22
# sudo apt-get install libblas3 liblapack3 liblapack-dev libblas-dev gfortran libatlas-base-dev

COPY lexpredict_openedgar/requirements/full.txt requirements.txt
RUN pip install -r requirements.txt