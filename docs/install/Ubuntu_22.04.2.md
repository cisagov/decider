# Ubuntu Desktop (Jammy) 22.04.2 LTS


## Install Script
- Assumes terminal bracketed paste mode is on (gnome default)
  - If it is off, a sudo prompt eats later lines of a pasted block
- See **ubuntu_22_04_2.sh** for the adventurous.. **otherwise just follow this file**
  - Not idempotent
  - No error handling
  - Doesn't ask you to change default passwords
  - Good for setup on a clean OS install


## Install Note
- Some files are created during the installation (in current dir)
  - Best to give yourself a temp dir
  - Make sure to delete this temp folder post-intall
```bash
cd
mkdir decider_temp
cd decider_temp
```


## Install Instructions


### Update Package Sources
- Ensures package listing is up-to-date
```bash
sudo apt update

# (optional)
# sudo apt upgrade
```


### Create Decider Service Account + Group
- Dedicated no-home, no-login, shell-less user prevents app from accessing more
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
git clone https://github.com/cisagov/decider.git
sudo cp -a ./decider/. /opt/decider/1.0.0
sudo chown -R decider:decider /opt/decider
```


### Install Python 3.8.10 (as Ubuntu 22.04 has Python 3.10.6)
- Useful as a means of isolation as well (never depends on system versions)
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
sudo mkdir /opt/decider/python3.8.10
sudo make altinstall
sudo chown -R decider:decider /opt/decider/python3.8.10
cd ..
```


### Create &amp; Populate virtualenv
- Useful instead of installing directly into Decider's own Py3.8.10 - as future versions could change packages in use
```bash
sudo -u decider -g decider /opt/decider/python3.8.10/bin/python3.8 -m \
    venv /opt/decider/1.0.0/venv/
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m \
    pip --no-cache-dir install -r /opt/decider/1.0.0/requirements-pre.txt
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m \
    pip --no-cache-dir install -r /opt/decider/1.0.0/requirements.txt
```


### Create user.json file &amp; Initialize DB
- **'Optional:'** Change default passwords in .env after copy command
```bash
sudo -u decider -g decider cp /opt/decider/1.0.0/.env.manual /opt/decider/1.0.0/.env
sudo -u decider -g decider chmod 660 /opt/decider/1.0.0/.env
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python /opt/decider/1.0.0/initial_setup.py
sudo -i -u postgres psql -a -f /opt/decider/1.0.0/init.sql
sudo -u decider -g decider rm /opt/decider/1.0.0/init.sql
```


### Configure Logging
- Logs DEBUG to decider.log and stdout by default
- [Configuring Logging](https://docs.python.org/3.8/howto/logging.html#configuring-logging)
```bash
# (optional)
# sudo -u decider -g decider nano --restricted /opt/decider/1.0.0/app/logging_conf.json
```


### Configure Content to be Built onto the DB (optional)
- ATT&amp;CK Enterprise v11.0 & v12.0 are built by default (as of Mar 2023)
  - This includes co-occurrences for each version (**Frequently Appears With** on Tech success pages)
- Configuration Information
  - Visit the **Admin Guide** (Decider_Admin_Guide_v1.0.0.pdf in docs)
  - Go to the section **Database Setup** (bottom of page 12)


### Build Database
```bash
cd /opt/decider/1.0.0/
sudo -u decider -g decider /opt/decider/1.0.0/venv/bin/python -m \
    app.utils.db.actions.full_build --config DefaultConfig
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
sudo -u decider -g decider RANDFILE=/opt/decider/1.0.0/app/utils/certs/.rnd openssl genrsa \
    -out /opt/decider/1.0.0/app/utils/certs/decider.key 2048
sudo -u decider -g decider RANDFILE=/opt/decider/1.0.0/app/utils/certs/.rnd openssl req -new \
    -key /opt/decider/1.0.0/app/utils/certs/decider.key \
    -out /opt/decider/1.0.0/app/utils/certs/decider.csr
sudo -u decider -g decider RANDFILE=/opt/decider/1.0.0/app/utils/certs/.rnd openssl x509 -req -days 365 \
    -in /opt/decider/1.0.0/app/utils/certs/decider.csr \
    -signkey /opt/decider/1.0.0/app/utils/certs/decider.key \
    -out /opt/decider/1.0.0/app/utils/certs/decider.crt
```


### Launch Decider
- Runs as a systemd service
```bash
# (optional - allows tweaking uwsgi threads, decider port, etc)
# sudo -u decider -g decider nano --restricted /opt/decider/1.0.0/uwsgi.ini

# (alternative - Decider can be launched without systemd)
# sudo /opt/decider/1.0.0/venv/bin/uwsgi --ini /opt/decider/1.0.0/uwsgi.ini

sudo cp /opt/decider/1.0.0/decider.service /etc/systemd/system/decider.service
sudo chmod 644 /etc/systemd/system/decider.service
sudo systemctl start decider
sudo systemctl status decider
sudo systemctl enable decider
```


### Default Login
- **email:** admin@admin.com
- **password:** admin
