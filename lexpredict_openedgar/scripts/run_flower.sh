source ../env/bin/activate
source .env
flower -A lexpredict_openedgar.taskapp --port=5555 --address=0.0.0.0
