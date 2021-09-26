#!/bin/bash
SCRIPT=`realpath $0`
SCRIPT_DIR=`dirname $SCRIPT`

if [[ -e "$SCRIPT_DIR/media_player.json" ]]
then
	port=`cat $SCRIPT_DIR/media_player.json|grep tcp_port|cut -d: -f2|cut -d, -f1|xargs`
else
	port='9090'
fi

connections=`lsof -i:$port|wc -l`

if [[ $connections -eq 0 ]]
	echo "Application media player is not available on port: $port"
else
	echo "Shutting down media player using port: $port"
fi