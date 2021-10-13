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
then
	echo "Starting application media player on port: $port"

	cd $SCRIPT_DIR
	python3 $SCRIPT_DIR/media_player.py
else
	echo "Application media player is already started on port: $port"
fi