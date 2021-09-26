#!/bin/bash
BASE_DIR="/opt/media_player"
USER="pi"
GROUP="users"

chmod u+rwX,g+rwX,o-w $BASE_DIR
chmod u+x,g+x,o-wx $BASE_DIR/*.sh
chown -R $USER.$GROUP $BASE_DIR
