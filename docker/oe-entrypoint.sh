#!/bin/bash

cd /opt/openedgar/lexpredict_openedgar
export PYTHONIOENCODING=utf-8
mkdir -p /data/logs

source ../env/bin/activate
source /opt/openedgar/default.env

source /opt/openedgar/dot_env.sh

export C_FORCE_ROOT="true"

service rabbitmq-server start

rabbitmqctl add_user openedgar openedgar

rabbitmqctl add_vhost openedgar

rabbitmqctl set_permissions -p openedgar openedgar ".*" ".*" ".*"

cd /opt/openedgar/tika

java -jar tika-server-1.21.jar > /data/logs/tika.log   2>&1 &

cd /opt/openedgar/lexpredict_openedgar

source ../env/bin/activate
source /opt/openedgar/default.env

# perform initial migration
python manage.py migrate

celery -A lexpredict_openedgar.taskapp worker --loglevel=INFO > /data/logs/celery.log  2>&1 &

python manage.py shell < run_edgar.py

tail -f /data/logs/celery.log
#| grep -v "INFO  rmeta/text (autodetecting type)"
