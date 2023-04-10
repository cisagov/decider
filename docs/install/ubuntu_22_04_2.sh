#!/bin/bash

# This is NOT idempotent
# This is intended for a fresh OS install
# This has no error handling

# temp dir for git clone & python building
cd
mkdir decider_temp
cd decider_temp

# ensure updated listing
sudo apt update

# decider service account
sudo adduser --no-create-home --system --shell /bin/false decider
sudo usermod -L decider
sudo groupadd decider
sudo usermod -aG decider decider

# install postgres
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo systemctl status postgresql

# clone repo
sudo apt install -y git
sudo mkdir /opt/decider
git clone https://github.com/cisagov/decider.git
sudo cp -a ./decider/. /opt/decider/1.0.0
sudo chown -R decider:decider /opt/decider

# build python 3.8.10
sudo apt install -y build-essential gdb lcov pkg-config \
    libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
    libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
    lzma lzma-dev tk-dev uuid-dev zlib1g-dev
wget https://www.python.org/ftp/python/3.8.10/Python-3.8.10.tar.xz
tar -xf Python-3.8.10.tar.xz
cd Python-3.8.10
./configure --prefix=/opt/decider/python3.8.10 --exec_prefix=/opt/decider/python3.8.10 --enable-optimizations
sudo mkdir /opt/decider/python3.8.10
sudo make altinstall
sudo chown -R decider:decider /opt/decider/python3.8.10
cd ..

# setup venv
sudo -u decider -g decider /opt/decider/python3.8.10/bin/python3.8 -m \
    venv /opt/decider/1.0.0/venv/
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m \
    pip --no-cache-dir install -r /opt/decider/1.0.0/requirements-pre.txt
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m \
    pip --no-cache-dir install -r /opt/decider/1.0.0/requirements.txt

# create user.json (for build), create/run/rm init.sql (for DB init)
sudo -u decider -g decider cp /opt/decider/1.0.0/.env.manual /opt/decider/1.0.0/.env
sudo -u decider -g decider chmod 660 /opt/decider/1.0.0/.env
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python /opt/decider/1.0.0/initial_setup.py
sudo -i -u postgres psql -a -f /opt/decider/1.0.0/init.sql
sudo -u decider -g decider rm /opt/decider/1.0.0/init.sql

# build database
cd /opt/decider/1.0.0/
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m \
    app.utils.db.actions.full_build --config DefaultConfig
sudo -u decider -g decider rm /opt/decider/1.0.0/app/utils/jsons/source/user.json

# generate self-signed ssl cert
sudo -u decider -g decider RANDFILE=/opt/decider/1.0.0/app/utils/certs/.rnd openssl genrsa \
    -out /opt/decider/1.0.0/app/utils/certs/decider.key 2048
sudo -u decider -g decider RANDFILE=/opt/decider/1.0.0/app/utils/certs/.rnd openssl req -new \
    -key /opt/decider/1.0.0/app/utils/certs/decider.key \
    -out /opt/decider/1.0.0/app/utils/certs/decider.csr
sudo -u decider -g decider RANDFILE=/opt/decider/1.0.0/app/utils/certs/.rnd openssl x509 -req -days 365 \
    -in /opt/decider/1.0.0/app/utils/certs/decider.csr \
    -signkey /opt/decider/1.0.0/app/utils/certs/decider.key \
    -out /opt/decider/1.0.0/app/utils/certs/decider.crt

# copy service file and start
sudo cp /opt/decider/1.0.0/decider.service /etc/systemd/system/decider.service
sudo chmod 644 /etc/systemd/system/decider.service
sudo systemctl start decider
sudo systemctl status decider
sudo systemctl enable decider
echo "Default Login: admin@admin.com admin"
