# Ubuntu Desktop (Jammy) 22.04.2 LTS


### Update Package Sources
```bash
sudo apt update

# (optional)
# sudo apt upgrade
```


### Create Decider Service Account + Group
```bash
sudo adduser --no-create-home --system --shell /bin/false decider
sudo usermod -L decider
sudo groupadd decider
sudo usermod -aG decider decider
```


### Install PostgreSQL
```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo systemctl status postgresql
```


### Clone Repository
```bash
sudo apt install -y git
sudo mkdir /opt/decider
sudo chown decider:decider /opt/decider
sudo -u decider -g decider git clone https://github.com/cisagov/decider.git /opt/decider/1.0.0
```


### Install Python 3.8.10 (as Ubuntu 22.04 has Python 3.10.6)
- [Build Dependencies Reference](https://devguide.python.org/getting-started/setup-building/index.html#install-dependencies)
```bash
sudo apt install -y build-essential gdb lcov pkg-config \
    libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
    libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
    lzma lzma-dev tk-dev uuid-dev zlib1g-dev

wget https://www.python.org/ftp/python/3.8.10/Python-3.8.10.tar.xz
tar -xf Python-3.8.10.tar.xz
cd Python-3.8.10

./configure --prefix=/opt/decider/python3.8.10 --exec_prefix=/opt/decider/python3.8.10 --enable-optimizations
make -j $(( $(nproc) + 1 ))

sudo mkdir /opt/decider/python3.8.10
sudo make altinstall
sudo chown -R decider:decider /opt/decider/python3.8.10

cd ..
sudo rm -rf Python-3.8.10
rm Python-3.8.10.tar.xz
```


### Create &amp; Populate virtualenv
```bash
sudo -u decider -g decider /opt/decider/python3.8.10/bin/python3.8 -m venv /opt/decider/1.0.0/venv/
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m pip --no-cache-dir install wheel==0.37.1
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m pip --no-cache-dir install -r /opt/decider/1.0.0/requirements.txt
```


### Create user.json file &amp; Initialize DB
```bash
sudo -u decider -g decider cp /opt/decider/1.0.0/.env.manual /opt/decider/1.0.0/.env
sudo -u decider -g decider chmod 660 /opt/decider/1.0.0/.env
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python /opt/decider/1.0.0/initial_setup.py
sudo -u postgres psql -a -f /opt/decider/1.0.0/init.sql
sudo -u decider -g decider rm /opt/decider/1.0.0/init.sql
```


### Configure Logging
- [Configuring Logging](https://docs.python.org/3.8/howto/logging.html#configuring-logging)
```bash
# (optional)
# sudo -u decider -g decider nano --restricted /opt/decider/1.0.0/app/logging_conf.yaml
```


### Build Database
```bash
cd /opt/decider/1.0.0/
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m app.utils.db.actions.full_build --config DefaultConfig
sudo -u decider -g decider rm /opt/decider/1.0.0/app/utils/jsons/source/user.json
```

### Add UFW Exception
```bash
# (optional - only needed if using & running UFW)
# sudo ufw allow 443/tcp
```


### Generate Self-Signed SSL Cert / Add Your Own
- **If you have your own cert already** - don't run the code, just write these 2 files:
  - /opt/decider/1.0.0/app/utils/certs/decider.key
  - /opt/decider/1.0.0/app/utils/certs/decider.crt
```bash
sudo -u decider -g decider openssl genrsa \
    -out /opt/decider/1.0.0/app/utils/certs/decider.key 2048
sudo -u decider -g decider openssl req -new \
    -key /opt/decider/1.0.0/app/utils/certs/decider.key \
    -out /opt/decider/1.0.0/app/utils/certs/decider.csr
sudo -u decider -g decider openssl x509 -req -days 365 \
    -in /opt/decider/1.0.0/app/utils/certs/decider.csr \
    -signkey /opt/decider/1.0.0/app/utils/certs/decider.key \
    -out /opt/decider/1.0.0/app/utils/certs/decider.crt
```


**ToDo: Remove** - Nukes and remakes Postgres
```bash
sudo pg_ctlcluster stop 14 main;
sudo systemctl stop postgresql;
sudo pg_dropcluster 14 main;
sudo systemctl start postgresql;
sudo pg_createcluster 14 main;
sudo pg_ctlcluster start 14 main;
sudo pg_ctlcluster status 14 main;
sudo systemctl status postgresql;
```