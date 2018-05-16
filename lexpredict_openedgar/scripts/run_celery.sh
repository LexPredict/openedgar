source ../env/bin/activate
source .env
celery -A lexpredict_openedgar.taskapp worker --loglevel=INFO -f celery.log -c16
