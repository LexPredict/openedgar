#!/bin/bash

cd /opt/openedgar/lexpredict_openedgar
export PYTHONIOENCODING=utf-8

source ../env/bin/activate
source /opt/openedgar/default.env

source /opt/openedgar/dot_env.sh

export C_FORCE_ROOT="true"

service rabbitmq-server start

rabbitmqctl add_user openedgar openedgar

rabbitmqctl add_vhost openedgar

rabbitmqctl set_permissions -p openedgar openedgar ".*" ".*" ".*"

# perform initial migration
python manage.py migrate

celery -A lexpredict_openedgar.taskapp worker --loglevel=INFO -f ./celery.log -c16 &

cd /opt/openedgar/tika

java -jar tika-server-1.20.jar > tika.log &

cd /opt/openedgar/lexpredict_openedgar
source ../env/bin/activate
source /opt/openedgar/default.env


python manage.py shell < run_edgar.py

tail -f celery.log