#!/bin/bash
SCRIPT=`realpath $0`
SCRIPT_DIR=`dirname $SCRIPT`

if [[ -e "$SCRIPT_DIR/media_player.json" ]]
then
	port=`cat $SCRIPT_DIR/media_player.json|grep http_port|cut -d: -f2|cut -d, -f1|xargs`
else
	port='9090'
fi

echo "Shutting down media player using port: $port"

curl -s -X POST http://127.0.0.1:$port/rest/app/shutdown >/dev/null

if [[ $? -eq 7 ]]
then
	echo "Application media player is not available on port: $port"
fi