rabbitmqctl add_user openedgar openedgar
rabbitmqctl add_vhost openedgar
rabbitmqctl set_permissions -p openedgar openedgar ".*" ".*" ".*"
rabbitmqctl set_user_tags openedgar administrator
