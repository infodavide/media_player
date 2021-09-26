#!/bin/bash
BASE_DIR="/opt/media_player"
LOCK_FILE=$BASE_DIR/media_player_update.lock
DATE_FILE=$BASE_DIR/media_player_update.dat
GIT_BRANCH="master"
GIT_URL="https://github.com/infodavide/media_player.git"
USER="pi"
GROUP="users"

function cleanup() {
	rm -f $LOCK_FILE>/dev/null 2>&1
}

if [[ -f $LOCK_FILE ]]; then
	exit 1
fi

trap cleanup EXIT
touch $LOCK_FILE
date --iso-8601>$DATE_FILE
cd $BASE_DIR
git version

if [ $? != 0 ]; then
	sudo apt-get install git
fi

if [[ -d $BASE_DIR/.git ]]; then
	echo "Upgrading application..."
	echo "Git command..."
	git pull origin "$GIT_BRANCH"
else
	echo "Installing application..."
	GROUP_EXISTS=`cat /etc/group|grep ^$GROUP | wc -l`

	if [[ "$GROUP_EXISTS" -eq "0" ]]; then
		echo "Creating group $GROUP..."
		sudo groupadd -r $GROUP
	else
		echo "Group $GROUP already exists"
	fi

	USER_EXISTS=`cat /etc/passwd|grep ^$USER | wc -l`

	if [[ "$USER_EXISTS" -eq "0" ]]; then
		echo "Creating user $USER..."
		sudo useradd -d $BASE_DIR -r -G $GROUP $USER
	else
		echo "User $USER already exists"
	fi

	echo "Git command..."
	git clone --no-checkout "$GIT_URL" $BASE_DIR/tmp
	mv $BASE_DIR/tmp/.git $BASE_DIR
	rm -fr $BASE_DIR/tmp
	cd $BASE_DIR
	git reset --hard HEAD
fi

echo "Setting permissions on user home"
sudo chown -R $USER.$GROUP $BASE_DIR
sudo chmod -R u+rwX,g+rwX,o+rX-w $BASE_DIR
usermod -aG $GROUP pi
chmod a+rwx $BASE_DIR/media_player_update.sh

if [[ -d $BASE_DIR/sudoers.d ]]; then
	echo "SUDO files..."
	sudo cp $BASE_DIR/sudoers.d/* /etc/sudoers.d
fi

if [[ -d $BASE_DIR/systemd ]]; then
	echo "Setting services..."
	for f in $BASE_DIR/systemd/*.service; do
		if [[ -f "$f" ]]; then
			bn=$(basename "$f")
			echo "Linking $f to /etc/systemd/system/$bn"
			rm -f /etc/systemd/system/$bn
			sudo ln -s $f /etc/systemd/system/$bn
			sudo systemctl daemon-reload
			sudo systemctl enable $bn
		else
			echo "$f is not a valid file"
		fi
	done
fi

echo "Installing python modules"
sudo python3 -m pip install --upgrade pip
sudo pip3 install requests flask-cors expiringdict PIL
sudo pip3 install numpy --upgrade
sudo pip3 install pillow --upgrade
sudo pip3 install pyautogui
sudo pip3 install netifaces
sudo pip3 install zeroconf
sudo pip3 install python-vlc
sudo pip3 install screeninfo
sudo pip3 install cv2
sudo pip3 install opencv-python

if [[ -d $BASE_DIR/python/* ]]; then
	for d in $BASE_DIR/python/* ; do
   		if [[ -d "$d" ]]; then
   			echo "Installing Python module $d"
   			sudo pip3 install "$d"
   		fi
	done
fi

echo "Installing applications"
sudo apt-get install vlc
sudo apt-get install libcblas-dev
sudo apt-get install libatlas-base-dev
sudo apt autoremove -y

cleanup
exit 0
