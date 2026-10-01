c = get_config()  # noqa: F821

# Le terminal ouvre un shell de login : /etc/profile.d/ros.sh est sourcé.
c.ServerApp.terminado_settings = {"shell_command": ["/bin/bash", "-l"]}

# rosbridge écoute seulement en local ; il n'est joignable qu'à travers
# le proxy authentifié du serveur Jupyter : /user/<nom>/rosbridge/
c.ServerProxy.servers = {
    "rosbridge": {
        "command": [
            "bash", "-lc",
            "exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml "
            "port:={port} address:=127.0.0.1",
        ],
        "timeout": 60,
        "launcher_entry": {"enabled": False},
    }
}
