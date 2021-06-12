#!/bin/bash
BASE_DIR="/opt/mediaplayer"
GIT_BRANCH="master"
USER="mediaplayer"
UPDATE_DATE_FILE="$BASE_DIR/media_player_update.dat"
UPDATE_SCRIPT="$BASE_DIR/media_player_update.sh"

cd "$BASE_DIR"

if [[ -f "$BASE_DIR/media_player_update.sh" ]]; then
	if test `find "$UPDATE_DATE_FILE" -mtime +1`; then
		echo "Checking last update..."
		bash "$UPDATE_SCRIPT"
	else
		echo "Update already checked..."
	fi
fi

if [[ -f "$BASE_DIR/media_player_update.sh" ]]; then
  python3 $BASE_DIR/media_player.py
else
  echo "Application not found..."
  exit 1
fi

exit 0
