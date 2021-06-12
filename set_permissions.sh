#!/bin/bash
chmod u+rwX,g+rwX,o-w /opt/media_player
chmod u+x,g+x,o-wx /opt/media_player/*.sh
chown -R mediaplayer.mediaplayer /opt/media_player
